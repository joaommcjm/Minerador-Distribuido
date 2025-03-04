import socket
import threading
import sys
import time
import hashlib

host = 'localhost'
porta = 31471

# Variável global para armazenar mensagens do servidor
ultima_mensagem = None
lock = threading.Lock()  # Controle de acesso à variável compartilhada


# Função para requisitar o nome do cliente
def get_client_name():
    while True:
        nome = input("Digite seu nome (máx. 10 caracteres):\m >>>> ").strip()
        if 1 <= len(nome) <= 10:
            if nome.isalpha():
                return nome.ljust(10)  # Ajusta a variável para ter exatamente 10 caracteres
            else:
                print("Nome inválido! Digite apenas letras.")
        else:
            print("Quantidade de caracteres inválida!")

# Thread que escuta mensagens do servidor
def listen_server(tcp_sock):
    global ultima_mensagem

    while True:
        try:
            dados = tcp_sock.recv(1024)
            if not dados:
                print("Servidor desconectado. Encerrando cliente.")
                sys.exit(1)

            # Garante que apenas uma thread acessa a última mensagem
            with lock:
                ultima_mensagem = dados  # Armazena a mensagem recebida
        except Exception as e:
            print(f"[ERRO] Falha ao receber mensagem do servidor: {e}")
            break


# Processa os dados da transação recebida e realiza a prova de trabalho (mineração).
def process_nonce(dados) -> tuple:

    # Decodifica os bytes de acordo com o protocolo
    id_transacao = int.from_bytes(dados[1:3], byteorder='big')      
    num_cliente = int.from_bytes(dados[3:5], byteorder='big')      
    tamanho_janela = int.from_bytes(dados[5:9], byteorder='big')   
    bits_zero = dados[9]                                            
    tam_transacao = int.from_bytes(dados[10:14], byteorder='big')   
    transacao = dados[14:14 + tam_transacao].decode('utf-8')       

    print(f"Transação recebida: {transacao} (ID: {id_transacao})")
    
    # Tenta achar o hash válido que corresponda ao nonce + transação
    nonce_encontrado = None
    for nonce in range(tamanho_janela):                             
        nonce_bytes = nonce.to_bytes(4, byteorder='big')         
        entrada_hash = nonce_bytes + transacao.encode('utf-8')  
        resultado_hash = hashlib.sha256(entrada_hash).hexdigest()   

        if resultado_hash.startswith('0' * bits_zero):              
            nonce_encontrado = nonce
            print(f"Nonce encontrado: {nonce} para a transação {id_transacao}")
            break
    
    return id_transacao, nonce_encontrado


# Envia um solicitação de transação ao servidor
def request_transaction(tcp_sock, client_name):
    global ultima_mensagem

    while True:

        # Envia um pedido de transação (protocolo G)
        msg = f"G{client_name}".encode("utf-8")
        tcp_sock.sendall(msg)
        print(f"[INFO] Solicitação de transação enviada: {msg.decode()}")

        # Aguarda resposta do servidor
        time.sleep(2)  # Pequeno delay para dar tempo de resposta do servidor

        with lock:
            if not ultima_mensagem:
                print("Nenhuma resposta do servidor. Tentando novamente...")
                continue
            dados = ultima_mensagem
            ultima_mensagem = None  # Limpa a variável para evitar reutilização indevida

        type = dados[0:1].decode('utf-8')  # Identifica o tipo de mensagem recebida


        # Servidor responde protocolo W (não há transações disponíveis)
        if type == 'W':  
            print("Nenhuma transação disponível. Aguardando...")
            time.sleep(10)
            continue
        

        if type == 'T': 
            id_transacao, nonce_encontrado = process_nonce(dados)

            if nonce_encontrado is not None:
                tcp_sock.send(b'S' + id_transacao.to_bytes(2, byteorder='big') + nonce_encontrado.to_bytes(4, byteorder='big'))
                print("Nonce enviado ao servidor!")
            else:
                print("Nonce não encontrado.")

        if len(dados) >= 3:  # Garante que `dados` tenha ao menos 3 bytes antes da conversão
            id_transacao = int.from_bytes(dados[1:3], byteorder='big')  # Extrai o ID da transação corretamente

        if type == 'V':
            print(f">>>>>>> Seu nonce foi validado para a transação {id_transacao}. <<<<<<<")
            print("[INFO] Validação confirmada pelo servidor.")

        elif type == 'R':
            print(f">>>>>>> Seu nonce foi rejeitado para a transação {id_transacao}. <<<<<<<")

        elif type == 'I':
            print(f"Um outro cliente encontrou um nonce para a transação {id_transacao}. Abortando tentativa atual...")
            print("[INFO] Processamento interrompido.")

        if type == 'Q':
            print("Servidor encerrando conexões. Saindo...")
            sys.exit(0)  # Encerra o cliente
        else:
            print("[ERRO] Dados recebidos são insuficientes para extrair id_transacao.")

        time.sleep(10)

def startClient():
    try:
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.connect((host, porta))
    except Exception as e:
        print ("Falha na conexão ao servidor.")
        sys.exit(2)
    return tcp_sock
        

def main():
    client_name = get_client_name()
    tcp_sock = startClient()

    # Cria as threads
    thread_listen = threading.Thread(target=listen_server, args=(tcp_sock,), daemon=True)
    thread_user_request = threading.Thread(target=request_transaction, args=(tcp_sock, client_name), daemon=True)
    #thread_server = threading.Thread(target=serverMessages(tcp_sock), daemon=True)

    print(f"Conectado em: {host, porta}")

    try: 
        thread_user_request.start()
        #thread_server.start()

        thread_user_request.join()
        #thread_server.join()
    except KeyboardInterrupt as e:
        print ("Finalizando por Cntl-C.") 

if __name__ == "__main__":
    main()