import socket
import ssl
import threading
import sys
import time
import json
import struct
import hashlib
import os

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

transacoes = {}  
transacoes_validas = {} 
clientes = {}           # Dicionário de clientes com suas respectivas conexões
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

# Processa o pedido do cliente de acordo com o protocolo
def process_request(my_conn, my_addr, type):
    
    #thread_atual = threading.current_thread()  # Obtém a thread atual
    #print(f"Executando na thread: {thread_atual.name} (ID: {thread_atual.ident})")
    #print(f'Processando pedido: {my_addr}, {type}!')
    #print("--------------------\n")
    
    global client_name
    global clientes

    #try:
        # Verifica se é um pedido de transação
    if type == b'G':  
        client_name = my_conn.recv(10).decode("utf-8").strip()  # Captura os 10 bytes do nome
        # Adiciona o cliente à lista de clientes
        clientes[client_name] = my_conn
        # Envia uma transação para o cliente
        enviar_transacao(my_conn, client_name)
    # Servidor precisa escutar se o cliente achou transação
    elif type == b'S':
        num_transacao = my_conn.recv(2)
        nonce = my_conn.recv(4)
        
        if processar_nonce(num_transacao, nonce, client_name):
            print(f"[INFO] Cliente {client_name} encontrou nonce válido para a transação {int.from_bytes(num_transacao, 'big')}.")
            # Registrar qual cliente encontrou o nonce primeiro
            transacoes_validas[num_transacao] = client_name

# Notificar os outros clientes
        for nome, cliente in clientes.items():
            if cliente != my_conn:
                    cliente.sendall(b'I' + num_transacao)
            else:
                    my_conn.sendall(b'R'+ num_transacao)

    elif type == b'V':
        num_transacao = my_conn.recv(2)
        print(f"[INFO] Transação {int.from_bytes(num_transacao, 'big')} validada.")
        
        transacoes_validas[num_transacao] = client_name
        
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

    #except Exception as e:
    #    print(f"[ERRO] Falha ao processar solicitação de {my_addr}: {e}")

# Adiciona novas transações
def gerar_transacoes(transacao, bits_zero):
        try:
            with lock:
                id_transacao = len(transacoes) + 1  # Gera um ID para a nova transação
                transacoes[id_transacao] = {
                    'transacao': transacao,
                    'bits_zero': bits_zero,
                    'clientes_validando': []  # Inicializa a lista de clientes validando a transação
                }
                print(f"Transação {id_transacao} adicionada com {bits_zero} bits zero.")
        except Exception as e:
            print(f"Erro ao adicionar transação: {e}.")

# Envia transação disponível para o cliente
def enviar_transacao(conn, client_name):
    #thread_atual = threading.current_thread()  # Obtém a thread atual
    #print(f"Executando na thread: {thread_atual.name} (ID: {thread_atual.ident})")
    #print("Enviando transação.")

    global tentativas
    with lock:
        # Verifica se existem transações
        if transacoes:
            transacao_pendente = False

            for trans in transacoes:
                if trans not in transacoes_validas.keys():
                    id_transacao = trans
                    dados_transacao = transacoes[id_transacao]
                    transacao_pendente = True
                    break

            # Envia 'W' caso todas as transações já estejam validadas
            if not transacao_pendente:
                conn.send(b'W')  
                return
        # Envia 'W' se não houver transações
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
    
    # Adiciona o cliente no dicionario de transações

    transacoes[id_transacao]['clientes_validando'].append(client_name)

    print(f"Enviando transação: \n{resposta}")
    print("--------------------\n")

    tentativas += 1

# Gerencia a comunicação com o cliente    
def process_client(my_conn, my_addr):
    
    #thread_atual = threading.current_thread()  # Obtém a thread atual
    #print(f"Executando na thread: {thread_atual.name} (ID: {thread_atual.ident})")
    #print(f'Novo cliente conectado: {my_addr}!')
    ("--------------------\n")
    
    all_conn.append(my_conn)                        # Adiciona o cliente à lista de conexões
    
    while True:
            type = my_conn.recv(1)                   # Recebe o primeiro byte da mensagem
            if not type:
                print(f"[ERRO] Tipo do protocolo inválido.")
                break # Cliente desconectou

            # Processa o pedido do cliente
            process_request(my_conn, my_addr, type)
        
    print(f"Cliente {my_addr} desconectado.") 
    all_conn.remove(my_conn)
    my_conn.close()

# Verifica se ononce enviado pelo cliente é válido
def processar_nonce(num_transacao, nonce, nome):
    print("PROCESSANDO NONCE")
    num_transacao = int.from_bytes(num_transacao, 'big')    # Obtém o ID da transação
    nonce = int.from_bytes(nonce, 'big')                    # Obtém o nonce enviado pelo cliente
    
    with lock:
        if num_transacao not in transacoes:
            return  # Ignora se a transação não existir mais
        
        transacao = transacoes[num_transacao]['transacao']  # Obtém os dados da transação
        bits_zero = transacoes[num_transacao]['bits_zero']  # Obtém o critério de bits zero
    
    entrada_hash = nonce.to_bytes(4, 'big') + transacao.encode('utf-8')
    resultado_hash = hashlib.sha256(entrada_hash).digest()  # Calcula o hash

    resultado_hash = bin(int.from_bytes(resultado_hash, 'big'))[2:].zfill(256)
    
    if resultado_hash.startswith('0' * bits_zero):
        with lock:
            transacoes_validas[num_transacao] = {'nonce': nonce, 'cliente': nome}  # Registra a transação validada
        print(f"\nNonce válido encontrado por {nome}: {nonce}")

        
        clientes[nome].send(f"V {num_transacao}".encode('utf-8'))  # Informa ao cliente que o nonce foi validado
        
        with lock:
            for outro_nome, cliente in clientes.items():  # Notifica os outros clientes
                if outro_nome != nome:
                    cliente.send(f"I {num_transacao}".encode('utf-8'))  # 'I' indica que outro cliente validou
            
    else:
        if nome in clientes:
            clientes[nome].send(f"R {num_transacao}".encode('utf-8'))  # 'R' indica rejeição do nonce


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
        print("Aguardando conexões...")
        print("--------------------\n")
        time.sleep(1)
        os.system('cls' if os.name == 'nt' else 'clear')
    except OSError:
        print("Erro ao inicializar, endereço em uso.")
        sys.exit(2)
    return sock

# Interage ocm o servidor via comandos sdo usuário
def interface_usuario():

    while True:
        print("\nComandos disponíveis:")
        print("=" * 70)
        print(f"| {'Comando':<15} | {'Descrição':<49} |")
        print("=" * 70)
        print(f"| {'/newtrans':<15} | {'Usuário deve informar transação para validar.':<49} |")
        print(f"| {'/validtrans':<15} | {'Mostra as transações já validadas.':<49} |")
        print(f"| {'/pendtrans':<15} | {'Mostra as transações pendentes.':<49} |")
        print(f"| {'/clients':<15} | {'Mostra os clientes e transações que validam.':<49} |")
        print("=" * 70)

        comando = input("\nDigite um comando:\n>>>> ").strip().lower()

        if comando == "/newtrans":
            transacao = input("Digite a transação a validar: ").strip()
            bits_zero = int(input("Número de bits zero necessários: ").strip())
            gerar_transacoes(transacao, bits_zero)

        elif comando == "/validtrans":
            with lock:
                if not transacoes_validas:
                    print("Nenhuma transação validada ainda.")
                else:
                    print("\nTransações Validadas:")
                    for num, info in transacoes_validas.items():
                        print(f"- ID {num}: Nonce {info['nonce']}, Validado por {info['cliente']}")

        elif comando == "/pendtrans":
            with lock:
                if not transacoes:
                    print("Nenhuma transação pendente.")
                else:
                    transacoes_pendentes = False
                    print("\nTransações Pendentes:")
                    for num, info in transacoes.items():
                        if num not in transacoes_validas:
                            print(f"- ID {num}: {info['transacao']}, {info['bits_zero']} bits zero, Clientes validando: {info['clientes_validando']}")
                            transacoes_pendentes = True
                    if not transacoes_pendentes:
                        print("Nenhuma transação pendente.")
                        

        elif comando == "/clients":
            with lock:
                # Checa se existem clientes
                if not clientes:
                    print("Nenhum cliente conectado.")
                else:
                    print("\nClientes Conectados:")
                    for cliente in clientes.keys():  # Iterando sobre o dicionário de clientes
                        transacoes_validando = []
                        # Verificando se o cliente está validando alguma transação
                        for num, dados_transacao in transacoes.items():
                            if cliente in dados_transacao['clientes_validando']:
                                transacoes_validando.append(f"ID {num}: {dados_transacao['transacao']} ({dados_transacao['bits_zero']} bits zero)")

                        if transacoes_validando:
                            print(f"- {cliente} validando: {', '.join(transacoes_validando)}")
                        else:
                            print(f"- {cliente}, sem transações.")     

        else:
            print("Comando inválido! Use: /newtrans, /validtrans, /pendtrans, /clients")

        #input("\nPressione Enter para continuar...")
        #os.system('cls' if os.name == 'nt' else 'clear')
def shutdown_server(sock):
    """ Encerra o servidor enviando 'Q' para os clientes e fechando conexões. """
    print("\n[INFO] Encerrando servidor...")

    # Envia 'Q' para todos os clientes conectados antes de encerrar
    for cliente in all_conn:
        try:
            cliente.sendall(b'Q')  # Mensagem de encerramento
            cliente.close()         # Fecha a conexão
        except Exception as e:
            print(f"[ERRO] Falha ao fechar conexão com cliente: {e}")

    sock.close()  # Fecha o socket do servidor
    print("[INFO] Servidor encerrado.")
    sys.exit(0)

def server_input_listener(sock):
    """ Thread que escuta comandos do usuário no terminal. """
    while True:
        comando = input()
        if comando.strip().upper() == "Q":
            shutdown_server(sock)

def main():
    print("Iniciando servidor...") 
    time.sleep(1)
    sock = startServer()

    thread_interface = threading.Thread(target=interface_usuario, daemon=True)
    thread_interface.start()
    
    thread_interface = threading.Thread(target=server_input_listener, args=(sock,), daemon=True)
    thread_interface.start()

    # Inicia a thread para ouvir as mensagens do Telegram
    #print("Iniciando thread para escutar mensagens do telegram...\n")
    #threading.Thread(target=telegram_listener, daemon=True).start()
    
    try:
        while True:
            conn, addr = sock.accept()
            t = threading.Thread(target=process_client, args=(conn, addr))
            all_threads.append(t)
            t.start()
    except KeyboardInterrupt: 
        print("\nEncerrando servidor...")
            

                # Enviar mensagem 'Q' para todos os clientes antes de encerrar
        for cliente in all_conn:
            try:
                cliente.sendall(b'Q')  # Indica que o servidor está fechando
                cliente.close()
            except:
                pass  # Ignora erros se o cliente já tiver desconectado
        
        sock.close()
        print("Servidor encerrado.")
        sys.exit(0)
    for t in all_threads:
        t.join()  # recolhe os processadores antes de fechar
    sock.close()

main()