import socket
import ssl
import threading
import sys
import time
import json
import struct
import hashlib

# Configuração do bot do Telegram
TOKEN = "7798685255:AAGzzDo2_5Nh0bwBt56qQVbv4Di7hGgZGww"
TELEGRAM_HOST = "api.telegram.org"
OFFSET = 0
chat_id = 670371979

# https://api.telegram.org/bot7798685255:AAGzzDo2_5Nh0bwBt56qQVbv4Di7hGgZGww/sendMessage?chat_id=670371979&text=oimeuamigo

HOST = 'localhost'
PORT = 31471
all_threads = []
all_conn = []
telegram_users = [chat_id]
transacoes_pendentes = []
transacoes_validadas = []

transacoes = {}  
transacoes_validas = {} 
clientes = {}
tentativas = 0
lock = threading.Lock() 

# Função para conectar ao Telegram e enviar requisições HTTP
def send_request_to_telegram(path):
        # Conecta ao servidor do Telegram na porta 443 (HTTPS)
        sock = socket.create_connection((TELEGRAM_HOST, 443))
        
        # Cria um contexto SSL
        context = ssl.create_default_context()
        ssl_sock = context.wrap_socket(sock, server_hostname=TELEGRAM_HOST)  # Cria uma conexão SSL
        
        # Requisição HTTP para o Telegram
        request = f"GET /{path} HTTP/1.1\r\n"
        request += f"Host: {TELEGRAM_HOST}\r\n"
        request += "Connection: close\r\n\r\n"
        ssl_sock.sendall(request.encode())
        
        # Recebe a resposta da requisição
        response = b""
        while True:
            part = ssl_sock.recv(4096)
            if not part:
                break
            response += part
        ssl_sock.close()

        thread_atual = threading.current_thread()  # Obtém a thread atual
        print(f"Resposta do Telegram atualizada. ({thread_atual.name})\n")
        
        # Verifica se a resposta contém um corpo antes de tentar processá-la
        if b"\r\n\r\n" in response:
            _, body = response.split(b"\r\n\r\n", 1)
            if not body.strip():  # Se estiver vazia, retorna um erro tratado
                print("Erro: resposta do Telegram está vazia.")
                return None  # Retorna None ao invés de tentar processar JSON inválido
            return json.loads(body)
        else:
            print("Erro: resposta do Telegram não contém cabeçalho e corpo esperados.")
            return None

# Obtém as mensagens enviadas ao bot no Telegram
def update_messages():
    global OFFSET
    updates = send_request_to_telegram(f"bot{TOKEN}/getUpdates?offset={OFFSET}&timeout=10")
    if updates and updates.get("ok"):
        return updates["result"]
    return []

# Envia mensagens do servidor para o Telegram
def send_message_telegram(chat_id, text):

    # Preparar Url para o request
    path = f"bot{TOKEN}/sendMessage?chat_id={chat_id}&text={text}"
    response = send_request_to_telegram(path)
    
    # Verifica se a resposta foi bem-sucedida
    if response and response.get("ok"):
        print(f"Mensagem enviada para {chat_id}: {text}")
    else:
        print(f"Falha ao enviar mensagem para {chat_id}: {response}")

# Distribui a mensagem para todos os clientes conectados e ao Telegram
def broadcast_message(my_conn, my_addr, msg):
    if my_addr != "Telegram":
        # Envia a mensagem para os usuários do Telegram
        for chat_id in telegram_users:
            send_message_telegram(chat_id, msg.decode("utf-8"))

    len_msg = len(msg).to_bytes(2, 'big')
    msg = len_msg + msg
    
    # Envia para todos os clientes conectados, exceto o remetente original
    for conn in all_conn:
        if conn != my_conn:  # não manda a msg para o próprio cliente que está enviando
            try:
                conn.send(msg)
            except Exception as e:
                print(f"Falha no envio a {my_addr}: {e}")

def handle_client(conn, addr):
    nome = conn.recv(1024).decode().strip()
    if not nome:
        conn.close()
        return
    
    with lock:
        clientes[nome] = conn
    print(f"{nome} conectado: {addr}")
    
    while True:
        try:
            conn.send(b"Digite um comando (/newtrans, /validtrans, /pendtrans, /clients): ")
            data = conn.recv(1024).decode().strip()
            if not data:
                break
            #####>>>>>>>>>>>>>>>>>>>>>>>>
            # 
            # 
            # 
            # 
            # #
            with lock:
                if data.startswith("/newtrans"):
                    _, transacao, bits_zero = data.split()
                    transacoes_pendentes.append((transacao, int(bits_zero), []))
                    conn.send(b"Transacao adicionada!\n")
                elif data == "/validtrans":
                    conn.send(str(transacoes_validadas).encode() + b"\n")
                elif data == "/pendtrans":
                    conn.send(str(transacoes_pendentes).encode() + b"\n")
                elif data == "/clients":
                    conn.send(str(clientes).encode() + b"\n")
                else:
                    conn.send(b"Comando invalido!\n")
        except Exception as e:
            print(f"Erro ao processar solicitação de {addr}: {e}")
            break
    ####
    # 
    # 
    # 
    # 
    # #
    with lock:
        del clientes[nome]
    conn.close()
    print(f"{nome} desconectado.")

# Processa o pedido do cliente de acordo com o protocolo
def process_request(my_conn, my_addr, type):
    
    thread_atual = threading.current_thread()  # Obtém a thread atual
    print(f"Executando na thread: {thread_atual.name} (ID: {thread_atual.ident})")

    print(f'Processando pedido: {my_addr}, {type}!')
    print("--------------------\n")

    try:
        # Verifica se é um pedido de transação
        if type == b'G':  
            client_name = my_conn.recv(10).decode("utf-8").strip()  # Captura os 10 bytes do nome
            print(f"[INFO] Cliente {client_name} ({my_addr}) solicitou uma transação.")
            
            # Envia uma transação para o cliente
            enviar_transacao(my_conn)

        # Servidor precisa escutar se o cliente achou transação
        elif type == b'S':
            num_transacao = my_conn.recv(2)
            nonce = my_conn.recv(4)
            process_nonce(num_transacao, nonce, client_name)
                
        elif type == b'V':
            num_transacao = my_conn.recv(2)
            print(f"[INFO] Transação {int.from_bytes(num_transacao, 'big')} validada.")
            
            global tentativas
            tentativas = 0

            # Enviar broadcast aqui

        elif type == b'R':
            num_transacao = my_conn.recv(2)
            print(f"[INFO] Transação {int.from_bytes(num_transacao, 'big')} rejeitada.")
        
        elif type == b'I':
            num_transacao = my_conn.recv(2)
            print(f"[INFO] Outro cliente encontrou nonce para a transação {int.from_bytes(num_transacao, 'big')}.")
        
        elif type == b'Q':
            print(f"[INFO] Recebido comando de encerramento do servidor.")
            my_conn.close()
            return  
        
        else:
            print(f"[ERRO] Tipo de requisição desconhecido de {my_addr}: {type}")

    except Exception as e:
        print(f"[ERRO] Falha ao processar solicitação de {my_addr}: {e}")

# Adiciona novas transações
def gerar_transacoes():
        try:
            bits_zero = 4
            with lock:
                id_transacao = len(transacoes) + 1  # Gera um ID para a nova transação
                transacao = f"Transação_{id_transacao}"
                transacoes[id_transacao] = {'transacao': transacao, 'bits_zero': bits_zero}
                print(f"Transação {id_transacao} adicionada.")
        except Exception as e:
            print(f"Erro ao adicionar transação: {e}.")

# Envia transação disponível para o cliente
def enviar_transacao(conn):
    thread_atual = threading.current_thread()  # Obtém a thread atual
    print(f"Executando na thread: {thread_atual.name} (ID: {thread_atual.ident})")

    global tentativas
    
    with lock:
        # Verifica se existem transações
        if transacoes:
            for trans in transacoes:
                if trans not in transacoes_validas:
                    id_transacao = trans
                    dados_transacao = transacoes[id_transacao]

        # Envia 'W' para indicar que não há transações disponíveis
        else:
            conn.send(b'W')  
            return
                
    
    transacao = dados_transacao['transacao'].encode('utf-8')  
    resposta = bytearray(b'T')                          # 'T' indica que é uma transação
    resposta.extend(id_transacao.to_bytes(2, 'big'))    # ID da transação (2 bytes)
    resposta.extend(len(clientes).to_bytes(2, 'big'))   # Número de clientes conectados (2 bytes)
    resposta.extend((1000000 * tentativas).to_bytes(4, 'big'))       # Janela de validação (4 bytes)
    resposta.append(dados_transacao['bits_zero'])       # Número de bits zero necessários
    resposta.extend(len(transacao).to_bytes(4, 'big'))  # Tamanho da transação (4 bytes)
    resposta.extend(transacao)                          # Dados da transação
    conn.send(resposta)                                 # Envia a transação ao cliente
    
    print(f"Enviando transação: \n{resposta}")
    print("--------------------\n")

    tentativas += 1

# Gerencia a comunicação com o cliente    
def client(my_conn, my_addr):
    
    thread_atual = threading.current_thread()  # Obtém a thread atual
    print(f"Executando na thread: {thread_atual.name} (ID: {thread_atual.ident})")

    print(f'Novo cliente conectado: {my_addr}!')
    print("--------------------\n")

    all_conn.append(my_conn)                        # Adiciona o cliente à lista de conexões
    prefix = f"{my_addr} digitou: ".encode('utf-8') # Identificação de quem enviou a mensagem 

    
    while True:
            type = my_conn.recv(1)                   # Recebe o primeiro byte da mensagem
            if not type:
                print(f"[ERRO] Tipo do protocolo inválido.")
                break # Cliente desconectou

            # Processa o pedido do cliente
            process_request(my_conn, my_addr, type)

            #msg = prefix + my_conn.recv(type)           # Lê a mensagem completa 
            #broadcast_message(my_conn, my_addr, msg)    # Envia a mensagem para os outros clientes
            #
            #thread_atual = threading.current_thread()   # Obtém a thread atual
            #print("--------------------")
            #print(f"Executando na thread: {thread_atual.name} (ID: {thread_atual.ident})")
            #print(f"Recebido:{msg.decode()}")
            #print("--------------------\n")

        
    print(f"Cliente {my_addr} desconectado.") 
    all_conn.remove(my_conn)
    my_conn.close()

# Verifica se ononce enviado pelo cliente é válido
def process_nonce(dados) -> tuple:

    # Decodifica os bytes de acordo com o protocolo
    id_transacao = int.from_bytes(dados[1:3], byteorder='big')      
    num_cliente = int.from_bytes(dados[3:5], byteorder='big')      
    tamanho_janela = int.from_bytes(dados[5:9], byteorder='big')   
    bits_zero = dados[9]                                            
    tam_transacao = int.from_bytes(dados[10:14], byteorder='big')   
    transacao = dados[14:14 + tam_transacao].decode('utf-8')        

    print(f"\nTransação recebida: {transacao} (ID: {id_transacao})")
    print(f"id_transacao: {id_transacao}")
    print(f"num_cliente: {num_cliente}")
    print(f"tamanho_janela: {tamanho_janela}")
    print(f"bits_zero: {bits_zero}")
    print(f"tam_transacao: {tam_transacao}")
    print(f"transacao: {transacao}")
    
    # Tenta achar o hash válido que corresponda ao nonce + transação
    nonce_encontrado = None
    start = tamanho_janela
    end = start + 1000000

    for nonce in range(start, end):
        print(f"Procurando nonce no range ({start}, {end}): {nonce}")                             
        nonce_bytes = nonce.to_bytes(4, byteorder='big')         
        entrada_hash = nonce_bytes + transacao.encode('utf-8')  
        resultado_hash = hashlib.sha256(entrada_hash).digest()   

        # Converte o hash para binário e verifica os bits iniciais
        resultado_hash = bin(int.from_bytes(resultado_hash, 'big'))[2:].zfill(256)
        print(resultado_hash)

        if resultado_hash.startswith('0' * bits_zero):              
            nonce_encontrado = nonce
            print(f"Nonce encontrado: {nonce} para a transação {id_transacao}")
            break
    
    return id_transacao, nonce_encontrado


# Obtém o último update_id do Telegram para evitar processamento de mensagens antigas
def get_latest_update_id():
    """ Obtém o último update_id para iniciar o OFFSET corretamente. """
    global telegram_users
    updates = send_request_to_telegram(f"bot{TOKEN}/getUpdates")
    if updates and updates.get("ok") and updates["result"]:
        return updates["result"][-1]["update_id"]  # Pega o último update_id
    return None  # Se não houver mensagens anteriores

# Captura mensagens enviadas ao bot no Telegram e repassa aos clientes
def telegram_listener():
     
    global OFFSET
    
    latest_update = get_latest_update_id()
    if latest_update is not None:
        OFFSET = latest_update + 1   

    try:
        while True:
            thread_atual = threading.current_thread()  # Obtém a thread atual
            print(f"Executando na thread: {thread_atual.name} (ID: {thread_atual.ident})")

            print("Atualizando mensagens...")
            updates = update_messages()
            for update in updates:
                OFFSET = update["update_id"] + 1
                if "message" in update:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"].get("text", "")

                    if chat_id not in telegram_users:
                        telegram_users.append(chat_id)

                    broadcast_message(None, "Telegram", f"[Telegram {chat_id}]: {text}".encode("utf-8"))
            time.sleep(10)
    except KeyboardInterrupt:
        print("Terminando thread de escuta ao telegram.")
        exit

# Cria o socket do servidor e inicia as conexões
def startServer():
    try:
        sock = socket.socket()  # flexibilidade de endereço
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # define e reutiliza PORTs já conectadas
        sock.bind((HOST, PORT))
        sock.listen()
        print("Servidor Iniciado!") 

        # Gera a primeira transação ao iniciar o servidor
        gerar_transacoes()

        print("Aguardando conexões...")
        print("--------------------\n")
    except OSError:
        print("Erro ao inicializar, endereço em uso.")
        sys.exit(2)
    return sock

def main():
    print("Iniciando servidor...") 
    time.sleep(0.5)
    sock = startServer()

    # Inicia a thread para ouvir as mensagens do Telegram
    #print("Iniciando thread para escutar mensagens do telegram...\n")
    #threading.Thread(target=telegram_listener, daemon=True).start()

    while True:
        try:
            conn, addr = sock.accept()
            print("\n--------------------")
            print("Iniciando thread com novo cliente...")
            t = threading.Thread(target=client, args=(conn, addr))
            all_threads.append(t)
            t.start()
        except Exception as e: 
            print(f"Erro ao aceitar conexão: {e}")
            break
        
    for t in all_threads:
        t.join()  # recolhe os processadores antes de fechar
    sock.close()

main()