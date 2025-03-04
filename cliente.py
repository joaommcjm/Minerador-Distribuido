import socket
import threading
import sys
import time
import hashlib

host = 'localhost'
porta = 31471

def get_client_name():
    while True:
        nome = input("Digite seu nome (máx. 10 caracteres):\n >>>> ").strip()
        if 1 <= len(nome) <= 10:
            if nome.isalpha():
                return nome.ljust(10)  
            else:
                print("Nome inválido! Digite apenas letras.")
        else:
            print("Quantidade de caracteres inválida!")

def request_transaction(tcp_sock, client_name):
    while True:
        msg = f"G{client_name}".encode("utf-8")
        
        tcp_sock.sendall(msg)
        print(f"[INFO] Solicitação de transação enviada: {msg.decode()}")

        try:
            dados = tcp_sock.recv(1024)
        except socket.error as e:
            print(f"Erro ao receber dados do servidor: {e}")
            break

        if not dados:
            print("Servidor não está respondendo. Encerrando cliente.")
            break
            
        type = dados[0:1].decode('utf-8')  

        if type == 'W':  
            print("Nenhuma transação disponível. Aguardando...")
            time.sleep(10)
            continue

        if type == 'T': 
            id_transacao = int.from_bytes(dados[1:3], byteorder='big')      
            num_cliente = int.from_bytes(dados[3:5], byteorder='big')      
            tamanho_janela = int.from_bytes(dados[5:9], byteorder='big')   
            bits_zero = dados[9]                                            
            tam_transacao = int.from_bytes(dados[10:14], byteorder='big')   
            transacao = dados[14:14 + tam_transacao].decode('utf-8')        

            print(f"Transação recebida: {transacao} (ID: {id_transacao})")
            
            nonce_encontrado = None
            for nonce in range(tamanho_janela):                             
                nonce_bytes = (nonce).to_bytes(4, byteorder='big')          
                entrada_hash = nonce_bytes + transacao.encode('utf-8')      
                resultado_hash = hashlib.sha256(entrada_hash).hexdigest()   
    
                if resultado_hash.startswith('0' * bits_zero):              
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

        tcp_sock.settimeout(5)  
        try:
            notificacao = tcp_sock.recv(1024).decode('utf-8')
            if notificacao.startswith("V"):
                print(f">>>>>>> Seu nonce foi validado para a transação {notificacao.split()[1]}. <<<<<<<")
            elif notificacao.startswith("R"):
                print(f">>>>>>> Seu nonce foi rejeitado para a transação {notificacao.split()[1]}. <<<<<<<")
            elif notificacao.startswith("I"):
                print(f"Um outro cliente encontrou um nonce para a transação {notificacao.split()[1]}.")
            elif notificacao.startswith("Q"):
                print("Servidor encerrando conexões. Você será desconectado.")
                break
        except socket.timeout:
            pass
        except socket.error as e:
            print(f"Erro ao receber notificação do servidor: {e}")
            break

        time.sleep(10)

def startClient():
    try:
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.connect((host, porta))
    except Exception as e:
        print("Falha na conexão ao servidor.")
        sys.exit(2)
    return tcp_sock

def main():
    client_name = get_client_name()
    tcp_sock = startClient()
    thread_user_request = threading.Thread(target=request_transaction, args=(tcp_sock, client_name), daemon=True)

    print(f"Conectado em: {host, porta}")

    try: 
        thread_user_request.start()
        thread_user_request.join()
    except KeyboardInterrupt as e:
        print("Finalizando por Cntl-C.") 

if __name__ == "__main__":
    main()