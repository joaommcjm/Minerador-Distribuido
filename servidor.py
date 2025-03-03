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
lock = threading.Lock() 

# Função para conectar ao Telegram e enviar requisições HTTP
def send_request_to_telegram(path):
    sock = socket.create_connection((TELEGRAM_HOST, 443))
    context = ssl.create_default_context()
    ssl_sock = context.wrap_socket(sock, server_hostname=TELEGRAM_HOST)
    
    request = f"GET /{path} HTTP/1.1\r\n"
    request += f"Host: {TELEGRAM_HOST}\r\n"
    request += "Connection: close\r\n\r\n"
    ssl_sock.sendall(request.encode())
    
    response = b""
    while True:
        part = ssl_sock.recv(4096)
        if not part:
            break
        response += part
    ssl_sock.close()

    thread_atual = threading.current_thread()
    print(f"Resposta do Telegram atualizada. ({thread_atual.name})\n")
    
    if b"\r\n\r\n" in response:
        _, body = response.split(b"\r\n\r\n", 1)
        if not body.strip():
            print("Erro: resposta do Telegram está vazia.")
            return None
        return json.loads(body)
    else:
        print("Erro: resposta do Telegram não contém cabeçalho e corpo esperados.")
        return None

def update_messages():
    global OFFSET
    updates = send_request_to_telegram(f"bot{TOKEN}/getUpdates?offset={OFFSET}&timeout=10")
    if updates and updates.get("ok"):
        return updates["result"]
    return []

def send_message_telegram(chat_id, text):
    path = f"bot{TOKEN}/sendMessage?chat_id={chat_id}&text={text}"
    response = send_request_to_telegram(path)
    
    if response and response.get("ok"):
        print(f"Mensagem enviada para {chat_id}: {text}")
    else:
        print(f"Falha ao enviar mensagem para {chat_id}: {response}")

def broadcast_message(my_conn, my_addr, msg):
    if my_addr != "Telegram":
        for chat_id in telegram_users:
            send_message_telegram(chat_id, msg.decode("utf-8"))

    len_msg = len(msg).to_bytes(2, 'big')
    msg = len_msg + msg
    
    for conn in all_conn:
        if conn != my_conn:
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
    
    with lock:
        del clientes[nome]
    conn.close()
    print(f"{nome} desconectado.")

def process_request(my_conn, my_addr, type):
    try:
        if type == b'G':  
            client_name = my_conn.recv(10).decode("utf-8").strip()
            print(f"[INFO] Cliente {client_name} ({my_addr}) solicitou uma transação.")
            enviar_transacao(my_conn)

        if type == b'S':
            num_transacao = my_conn.recv(2)
            nonce = my_conn.recv(4)
            processar_nonce(num_transacao, nonce, client_name)
                
        else:
            print(f"[ERRO] Tipo de requisição desconhecido de {my_addr}: {type}")

    except Exception as e:
        print(f"[ERRO] Falha ao processar solicitação de {my_addr}: {e}")

def gerar_transacoes():
    try:
        bits_zero = 32
        with lock:
            id_transacao = len(transacoes) + 1
            transacao = f"Transação_{id_transacao}"
            transacoes[id_transacao] = {'transacao': transacao, 'bits_zero': bits_zero}
            print(f"[INFO] Transação {id_transacao} gerada: {transacao}.")
            print(f"Transação {id_transacao} adicionada.")
    except Exception as e:
        print(f"Erro ao adicionar transação: {e}.")

def enviar_transacao(conn):
    with lock:
        if transacoes:
            for trans in transacoes:
                if trans not in transacoes_validas:
                    id_transacao = trans
                    dados_transacao = transacoes[id_transacao]
                    print(f"[INFO] Enviando transação {id_transacao} para o cliente.")
                    break
        else:
            print("[INFO] Nenhuma transação disponível para enviar")
            conn.send(b'W')  
            return
                
    transacao = dados_transacao['transacao'].encode('utf-8')  
    resposta = bytearray(b'T')                          
    resposta.extend(id_transacao.to_bytes(2, 'big'))    
    resposta.extend(len(clientes).to_bytes(2, 'big'))   
    resposta.extend((1000000).to_bytes(4, 'big'))       
    resposta.append(dados_transacao['bits_zero'])       
    resposta.extend(len(transacao).to_bytes(4, 'big'))  
    resposta.extend(transacao)                          
    conn.send(resposta)
    print(f"[INFO] Transação {id_transacao} enviada: {transacao.decode()}")                                 

def client(my_conn, my_addr):
    thread_atual = threading.current_thread()
    print(f"Executando na thread: {thread_atual.name} (ID: {thread_atual.ident})")

    print(f'Novo cliente conectado: {my_addr}!')
    print("--------------------\n")

    all_conn.append(my_conn)                        
    prefix = f"{my_addr} digitou: ".encode('utf-8') 

    while True:
        try:
            type = my_conn.recv(1)                   
            if type == b'G':
                client_name = my_conn.recv(10).decode("utf-8").strip()
            if not type:
                print(f"[ERRO] Tipo do protocolo inválido.")
                break 

            process_request(my_conn, my_addr, type)

            msg = prefix + my_conn.recv(type)           
            broadcast_message(my_conn, my_addr, msg)    

            thread_atual = threading.current_thread()   
            print("--------------------")
            print(f"Executando na thread: {thread_atual.name} (ID: {thread_atual.ident})")
            print(f"Recebido:{msg.decode()}")
            print("--------------------\n")
        except Exception as e:
            print("Falha no processamento do cliente ", my_addr, "ERRO:", e)
            break
        
    print(f"Cliente {my_addr} desconectado.") 
    all_conn.remove(my_conn)
    my_conn.close()

def processar_nonce(num_transacao, nonce, nome):
    num_transacao = int.from_bytes(num_transacao, 'big')    
    nonce = int.from_bytes(nonce, 'big')                    

    with lock:
        if num_transacao not in transacoes:
            return  
        
        transacao = transacoes[num_transacao]['transacao']  
        bits_zero = transacoes[num_transacao]['bits_zero']  
        
    entrada_hash = nonce.to_bytes(4, 'big') + transacao.encode('utf-8')
    resultado_hash = hashlib.sha256(entrada_hash).hexdigest()  

    if resultado_hash.startswith('0' * bits_zero):
        with lock:
            transacoes_validas[num_transacao] = {'nonce': nonce, 'cliente': nome}  
        print(f"\nNonce válido encontrado por {nome}: {nonce}")
        
        clientes[nome].send(f"V {num_transacao}".encode('utf-8'))  
        
        with lock:
            for outro_nome, cliente in clientes.items():  
                if outro_nome != nome:
                    cliente.send(f"I {num_transacao}".encode('utf-8'))  
            
            for cliente in clientes.values():  
                cliente.send(b'Q')
        
        print("Servidor encerrando conexões com os clientes...")
        exit()  
    else:
        if nome in clientes:
            clientes[nome].send(f"R {num_transacao}".encode('utf-8'))  

def get_latest_update_id():
    global telegram_users
    updates = send_request_to_telegram(f"bot{TOKEN}/getUpdates")
    if updates and updates.get("ok") and updates["result"]:
        return updates["result"][-1]["update_id"]  
    return None  

def telegram_listener():
    global OFFSET
    
    latest_update = get_latest_update_id()
    if latest_update is not None:
        OFFSET = latest_update + 1   

    try:
        while True:
            thread_atual = threading.current_thread()  
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
        exit()

def check_inactive_clients():
    while True:
        time.sleep(60)  
        with lock:
            for nome, conn in list(clientes.items()):
                if conn is None:  
                    continue
                try:
                    conn.send(b'')  
                except:
                    print(f"Cliente {nome} desconectado por inatividade.")
                    del clientes[nome]  

def startServer():
    try:
        sock = socket.socket()  
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  
        sock.bind((HOST, PORT))
        sock.listen(5)
        print("Servidor Iniciado!") 

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

    threading.Thread(target=telegram_listener, daemon=True).start()
    threading.Thread(target=check_inactive_clients, daemon=True).start()

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
        t.join()  
    sock.close()

main()