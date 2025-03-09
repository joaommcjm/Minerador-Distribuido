import socket
import ssl
import threading
import sys
import time
import json
import hashlib
import os

# Configuração do bot do Telegram
TOKEN = "7798685255:AAGzzDo2_5Nh0bwBt56qQVbv4Di7hGgZGww"
TELEGRAM_HOST = "api.telegram.org"
OFFSET = 0
chat_id = 670371979

HOST = 'localhost'
PORT = 31471
all_conn = []
all_threads = []
telegram_users = [chat_id]

transacoes = {}  
transacoes_validas = {} 
clientes = {}           
tentativas = 0
serverIsRunning = True
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
        #print(f"Resposta do Telegram atualizada. ({thread_atual.name})\n")
        
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
    with lock:
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
        None
        #print(f"Mensagem enviada para {chat_id}: {text}")
    else:
        print(f"Falha ao enviar mensagem para {chat_id}: {response}")

# Distribui a mensagem para todos os clientes conectados e ao Telegram
def broadcast_message(my_conn, my_addr, msg):
    if my_addr != "Telegram":
        # Envia a mensagem para os usuários do Telegram
        with lock:
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
    global clients

    #try:
        # Verifica se é um pedido de transação
    if type == b'G':  
        client_name = my_conn.recv(10).decode("utf-8").strip()  # Captura os 10 bytes do nome
        clientes[client_name] = my_conn                         # Adiciona o cliente à lista de clientes

        # Envia uma transação para o cliente
        enviar_transacao(my_conn, client_name)
        time.sleep(5)

    # Servidor precisa escutar se o cliente achou transação
    elif type == b'S':
        num_transacao = my_conn.recv(2)
        nonce = my_conn.recv(4)
        processar_nonce(num_transacao, nonce, client_name)
            
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

                    transacoes[id_transacao]['clientes_validando'].append(client_name)
                    local_tentativas = tentativas
                    tentativas += 1
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
    resposta.extend((1000000 * local_tentativas).to_bytes(4, 'big'))       # Janela de validação (4 bytes)
    resposta.append(dados_transacao['bits_zero'])       # Número de bits zero necessários
    resposta.extend(len(transacao).to_bytes(4, 'big'))  # Tamanho da transação (4 bytes)
    resposta.extend(transacao)                          # Dados da transação
    conn.send(resposta)                                 # Envia a transação ao cliente
    
    # Adiciona o cliente no dicionario de transações

    print(f"\nEnviando transação: \n{resposta}")
    print("--------------------\n")



# Gerencia a comunicação com o cliente    
def client(my_conn, my_addr):
    
    all_conn.append(my_conn)                        # Adiciona o cliente à lista de conexões
    try:
        while True:
                type = my_conn.recv(1)                   # Recebe o primeiro byte da mensagem
                if not type:
                    print(f"[ERRO] Tipo do protocolo inválido.")
                    break # Cliente desconectou

                    # Processa o pedido do cliente
                process_request(my_conn, my_addr, type)
    except:

        # Remove o cliente do dicionário de clientes
        client_name = None
        for name, conn in clientes.items():
            if conn == my_conn:
                client_name = name

        if client_name is not None:
            del clientes[client_name]

        try:
            all_conn.remove(my_conn)
        except ValueError:
            None
        finally:
            my_conn.close()  # Certifique-se de fechar a conexão corretamente
            print(f"Conexão com o cliente {my_addr} encerrada.")

# Verifica se ononce enviado pelo cliente é válido
def processar_nonce(num_transacao, nonce, nome):

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
        clientes[nome].send(b'V' + num_transacao.to_bytes(2, 'big')) # Informa ao cliente que o nonce foi validado
        with lock:
            for outro_nome, conexao in clientes.items():  # Notifica os outros clientes

                if outro_nome != nome:
                    print(f"Enviando I para {outro_nome}")
                    conexao.send(b'I' + num_transacao.to_bytes(2, 'big'))   # 'I' indica que outro cliente validou
            
    else:
        if nome in clientes:
            print(f"Enviando R para {nome}")
            clientes[nome].send(b'R' + num_transacao.to_bytes(2, 'big'))  # 'R' indica rejeição do nonce


# Obtém o último update_id do Telegram para evitar processamento de mensagens antigas
def get_latest_update_id():
    """ Obtém o último update_id para iniciar o OFFSET corretamente. """
    global telegram_users
    with lock:
        updates = send_request_to_telegram(f"bot{TOKEN}/getUpdates")
    if updates and updates.get("ok") and updates["result"]:
        return updates["result"][-1]["update_id"]  # Pega o último update_id
    return None  # Se não houver mensagens anteriores

# Captura mensagens enviadas ao bot no Telegram e repassa aos clientes
def telegram_listener():
    global OFFSET, telegram_users
    
    latest_update = get_latest_update_id()
    if latest_update is not None:
        with lock:
            OFFSET = latest_update + 1
    
    try:
        while True:
            #thread_atual = threading.current_thread()
            #print(f"Executando na thread: {thread_atual.name} (ID: {thread_atual.ident})")
            #print("Atualizando mensagens...")

            updates = update_messages()
            for update in updates:
                with lock:
                    OFFSET = update["update_id"] + 1
                if "message" in update:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"].get("text", "").strip()
                    
                    with lock:
                        if chat_id not in telegram_users:
                            telegram_users.append(chat_id)
                    
                    interface_usuario(text, chat_id)
                    
                    #broadcast_message(None, "Telegram", f"[Telegram {chat_id}]: {text}".encode("utf-8"))
                    #send_message_telegram(chat_id, resposta)
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("Terminando thread de escuta ao telegram.")
        time.sleep(1)
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
        time.sleep(10)
        sys.exit(2)
    return sock

def shutdown_server():
    global running
    running = False
    print("Encerrando o servidor...")

    for conn in all_conn:
        try:
            conn.send(b'Q')
            conn.close()
        except:
            pass

    all_conn.clear()  # Limpa conexões ativas
    print("Todas as conexões foram encerradas.")

    for thread in all_threads:
        thread.join()

    print("Servidor desligado.")
    sys.exit(0)


# Interage ocm o servidor via comandos sdo usuário
def interface_usuario(comando=None, chat_id=None):
    # Se a função é chamado com comando=None significa que ela foi chamada pelo servidor
    if comando is None:
        while True:
            print("\nComandos disponíveis:")
            print("=" * 70)
            print(f"| {'Comando':<15} | {'Descrição':<49} |")
            print("=" * 70)
            print(f"| {'/newtrans':<15} | {'Usuário deve informar transação para validar.':<49} |")
            print(f"| {'/validtrans':<15} | {'Mostra as transações já validadas.':<49} |")
            print(f"| {'/pendtrans':<15} | {'Mostra as transações pendentes.':<49} |")
            print(f"| {'/clients':<15} | {'Mostra os clientes e transações que validam.':<49} |")
            print(f"| {'/quit':<15} | {'Desconecta todos os clientes e encerra o servidor.':<49} |")
            print("=" * 70)
            try:
                comando = input("\nDigite um comando:\n>>>> ").strip().lower()
                resposta = processar_comando(comando)
                #os.system('cls' if os.name == 'nt' else 'clear')
                if resposta != "":
                    print("------------------------------------------------------------")
                    print(f"{resposta}")
                    print("------------------------------------------------------------\n")
            except Exception as e:  # Captura outros erros genéricos
                None
                #print(f"\n[ERRO]: {e}")
            
    # Se a função é chamada e tem um argumento significa que ela vem do telegram
    else:
        resposta = processar_comando(comando, chat_id)
        send_message_telegram(chat_id, resposta)

def processar_comando(comando, chat_id=None) -> str:
    resposta = ""
    with lock:
        if comando == "/newtrans":
            # Se processar comando não é invocado pelo telegram
            if not chat_id:
                transacao = input("Digite a transação a validar: ").strip()

                try:
                    bits_zero = int(input("Número de bits zero necessários: ").strip())
                except:
                    resposta = "Número de bits zero inválido."
                    return resposta
                    

                if transacao.isalpha() and type(bits_zero) == int:
                    gerar_transacoes(transacao, bits_zero)
                else:
                    resposta = "Nome da transação inválida."

            else:
                resposta = "Comando inválido para o usuário Telegram."
        elif comando == "/validtrans":
                if not transacoes_validas:
                    resposta = "Nenhuma transação validada ainda."
                else:
                    print("Transações Validadas:")
                    for num, info in transacoes_validas.items():
                         resposta += f"- ID {num}: Nonce {info['nonce']}, Validado por {info['cliente']}"

        elif comando == "/pendtrans":
                if not transacoes:
                    resposta = "Nenhuma transação pendente."
                else:
                    transacoes_pendentes = False
                    resposta = "Transações Pendentes:"
                    for num, info in transacoes.items():
                        if num not in transacoes_validas:
                            resposta += f"- ID {num}: {info['transacao']}, {info['bits_zero']} bits zero, Clientes validando: {info['clientes_validando']}"
                            transacoes_pendentes = True
                    if not transacoes_pendentes:
                        resposta = "Nenhuma transação pendente."

        elif comando == "/clients":
                # Checa se existem clientes
                if not clientes:
                    resposta = "Nenhum cliente conectado."
                else:
                    resposta = "Clientes Conectados:"
                    for cliente in clientes.keys():  # Iterando sobre o dicionário de clientes
                        transacoes_validando = []
                        # Verificando se o cliente está validando alguma transação
                        for num, dados_transacao in transacoes.items():
                            if cliente in dados_transacao['clientes_validando']:
                                transacoes_validando.append(f"ID {num}: {dados_transacao['transacao']} ({dados_transacao['bits_zero']} bits zero)")
                        if transacoes_validando:
                            resposta += f"- {cliente} validando: {', '.join(transacoes_validando)}"
                        else:
                            resposta += f"- {cliente}, sem transações."
        elif comando == "/quit":
            if not chat_id:
                shutdown_server()
            else:
                resposta = "Comando inválido para o telegram." 
        else:
            resposta = "Comando inválido! Use: /newtrans, /validtrans, /pendtrans, /clients, /quit"
    return resposta


def main():
    print("Iniciando servidor...") 
    time.sleep(1)
    
    # Inicia a thread para ouvir as mensagens do Telegram
    sock = startServer()

    # Inicia a thread para a interface do usuário
    thread_interface = threading.Thread(target=interface_usuario, daemon=True)
    thread_interface.start()

    # Inicia a thread para ouvir as mensagens do Telegram
    thread_telegram = threading.Thread(target=telegram_listener, daemon=True)
    thread_telegram.start()


    while serverIsRunning:
        try:
            conn, addr = sock.accept()
            thread_client = threading.Thread(target=client, args=(conn, addr))
            all_threads.append(thread_client)
            thread_client.start()
        except Exception as e: 
            print(f"Erro ao aceitar conexão: {e}")
            break
        
    # Espera todas as threads terminarem antes de fechar o servidor    
    for t in all_threads:
        t.join()
    sock.close()
    print("Servidor encerrado.")

main()