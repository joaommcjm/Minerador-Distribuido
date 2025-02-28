import socket
import json
import hashlib
import time

# Configurações do cliente
HOST = '127.0.0.1'
PORTA = 31471
NOME_CLIENTE = 'Cliente1'

def solicitar_transacao(sock):
    sock.send(NOME_CLIENTE.encode('utf-8').ljust(10))
    while True:
        sock.send(json.dumps({'tipo': 'G'}).encode('utf-8'))  # Pedido de transação
        dados = sock.recv(1024)
        mensagem = json.loads(dados.decode('utf-8'))

        if mensagem['tipo'] == 'W':
            print("Nenhuma transação disponível. Aguardando...")
            time.sleep(10)  # Esperar 10 segundos antes de pedir novamente
            continue
        
        # Processar resposta do servidor
        id_transacao = mensagem['id_transacao']
        num_clientes = mensagem['num_clientes']
        tamanho_janela = mensagem['tamanho_janela']
        bits_zero = mensagem['bits_zero']
        transacao = mensagem['transacao']
        print(f"Transação recebida: {transacao} (ID: {id_transacao})")
        
        # Tentar encontrar o nonce
        for nonce in range(tamanho_janela):
            entrada_hash = str(nonce).encode('utf-8') + transacao.encode('utf-8')
            resultado_hash = hashlib.sha256(entrada_hash).hexdigest()
            if resultado_hash.startswith('0' * bits_zero):
                print(f"Nonce encontrado: {nonce} para a transação {id_transacao}")
                sock.send(json.dumps({'tipo': 'S', 'id_transacao': id_transacao, 'nonce': nonce}).encode('utf-8'))
                break

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORTA))
    solicitar_transacao(sock)
    sock.close()

if __name__ == "__main__":
    main()