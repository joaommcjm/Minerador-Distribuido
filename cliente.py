import socket
import threading
import sys
import time
import hashlib

host = 'localhost'
porta = 31471

# Função para requisitar o nome do cliente
def get_client_name():
    while True:
        nome = input("Digite seu nome (máx. 10 caracteres):\n >>>> ").strip()
        if 1 <= len(nome) <= 10:
            if nome.isalpha():
                return nome.ljust(10)  # Ajusta a variável para ter exatamente 10 caracteres
            else:
                print("Nome inválido! Digite apenas letras.")
        else:
            print("Quantidade de caracteres inválida!")

# Envia um solicitação de transação ao servidor
def request_transaction(tcp_sock, client_name):
    
    while True:

        # Envia um pedido de transação (protocolo G)
        msg = f"G{client_name}".encode("utf-8")
        tcp_sock.sendall(msg)
        print(f"[INFO] Solicitação de transação enviada: {msg.decode()}")

        # Aguarda resposta do servidor
        dados = tcp_sock.recv(1024)

        if not dados:
            print("Servidor não está respondendo. Encerrando cliente.")
            break
            
        type = dados[0:1].decode('utf-8')  # Identifica o tipo de mensagem recebida

        # Servidor responde protocolo W (não há transações disponíveis)
        if type == 'W':  
            print("Nenhuma transação disponível. Aguardando...")
            time.sleep(10)
            continue
        
        if type == 'T': 
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
            for nonce in range(tamanho_janela):                             # Itera sobre a janela de tentativa
                nonce_bytes = (nonce).to_bytes(4, byteorder='big')          # Converte nonce para bytes
                entrada_hash = nonce_bytes + transacao.encode('utf-8')      # Cria entrada para hash
                resultado_hash = hashlib.sha256(entrada_hash).hexdigest()   # Calcula hash SHA-256
                
                if resultado_hash.startswith('0' * bits_zero):              # Verifica se o hash atende à condição
                    nonce_encontrado = nonce
                    print(f"Nonce encontrado: {nonce} para a transação {id_transacao}")
                    break
            
            if nonce_encontrado is not None:
                while True:
                    resposta = input("Encontrou o nonce? Pressione 'S' para validar: ").strip().upper()
                    if resposta == 'S':
                        tcp_sock.send(b'S' + id_transacao.to_bytes(2, byteorder='big') + (nonce_encontrado).to_bytes(4, byteorder='big'))
                        print("Nonce enviado ao servidor!")
                        break
                    else:
                        print("Entrada inválida. Pressione 'S' para validar o nonce.")
        # Recebe notificações do servidor
        tcp_sock.settimeout(5)  # Define um tempo limite para evitar travamentos
        try:
            notificacao = tcp_sock.recv(1024).decode('utf-8')
            if notificacao.startswith("V"):
                print(f">>>>>>> Seu nonce foi validado para a transação {notificacao.split()[1]}. <<<<<<<")
            elif notificacao.startswith("R"):
                print(f">>>>>>> Seu nonce foi rejeitado para a transação {notificacao.split()[1]}. <<<<<<<")
            elif notificacao.startswith("I"):
                print(f"Um outro cliente encontrou um nonce para a transação {notificacao.split()[1]}.")
        except socket.timeout:
            pass

        time.sleep(10)

def userMessages(tcp_sock):
    while True:
        try:
            msg = input("> ")
            if msg:
                len_msg =  len(msg.encode('utf-8')).to_bytes(2, 'big') #2 bytes do tamanho 
                msg = len_msg + msg.encode("utf-8")
                tcp_sock.sendall(msg)
        except Exception as e:
            print("Fechamento do input() ou servidor.\nFechando conexão com o servidor")
            tcp_sock.close()
            break
 
def serverMessages(tcp_sock):
    while True:
        try:
            len_msg = int.from_bytes(tcp_sock.recv(2),'big')
            bytes_msg = tcp_sock.recv(len_msg) #recebe a string da msg
            msg = bytes_msg.decode("utf-8")
            if msg:
                print(f"Recebido: {msg}\n> ")
        except Exception as e:
            print(f"Conexão fechada pelo servidor.")
            break
    
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
    thread_user = threading.Thread(target=userMessages, args=(tcp_sock,), daemon=True)# Threads das funções
    thread_server = threading.Thread(target=serverMessages, args=(tcp_sock,), daemon=True)

    print(f"Conectado em: {host, porta}")

    try: 
        thread_user.start()
        thread_server.start()

        thread_user.join()
        thread_server.join()
    except KeyboardInterrupt as e:
        print ("Finalizando por Cntl-C.") 

if __name__ == "__main__":
    main()