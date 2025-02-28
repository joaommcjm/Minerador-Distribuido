import socket
import threading
import hashlib
import json
import time

# Configurações do servidor
HOST = '127.0.0.1'
PORTA = 31471

# Armazenamento de transações
transacoes = {}
clientes = {}

def tratar_cliente(conn, addr):
    print(f"Conexão de {addr} estabelecida.")
    nome = conn.recv(10).decode('utf-8').strip()
    clientes[nome] = conn

    while True:
        try:
            dados = conn.recv(1024)
            if not dados:
                break
            
            # Processar mensagens do cliente
            mensagem = json.loads(dados.decode('utf-8'))
            if mensagem['tipo'] == 'G':
                # Pedido de transação
                if transacoes:
                    # Enviar transação disponível
                    id_transacao, dados_transacao = transacoes.popitem()
                    resposta = criar_resposta_transacao(id_transacao, dados_transacao, nome)
                    conn.send(resposta.encode('utf-8'))
                else:
                    # Não há transações disponíveis
                    conn.send(json.dumps({'tipo': 'W'}).encode('utf-8'))
            elif mensagem['tipo'] == 'S':
                # Receber nonce encontrado
                id_transacao = mensagem['id_transacao']
                nonce = mensagem['nonce']
                validar_nonce(id_transacao, nonce, nome)
        except Exception as e:
            print(f"Erro: {e}")
            break

    conn.close()
    del clientes[nome]
    print(f"Conexão de {addr} encerrada.")

def criar_resposta_transacao(id_transacao, dados_transacao, nome):
    # Montar a resposta para o cliente
    resposta = {
        'tipo': 'T',
        'id_transacao': id_transacao,
        'num_clientes': len(clientes),
        'tamanho_janela': 1000000,  # Tamanho da janela de validação
        'bits_zero': dados_transacao['bits_zero'],
        'transacao': dados_transacao['transacao']
    }
    return json.dumps(resposta)

def validar_nonce(id_transacao, nonce, nome):
    # Validação do nonce
    dados_transacao = transacoes.get(id_transacao)
    if dados_transacao:
        transacao = dados_transacao['transacao']
        bits_zero = dados_transacao['bits_zero']
        entrada_hash = str(nonce).encode('utf-8') + transacao.encode('utf-8')
        resultado_hash = hashlib.sha256(entrada_hash).hexdigest()
        
        if resultado_hash.startswith('0' * bits_zero):
            # Notificar todos os clientes sobre o nonce válido
            for cliente in clientes.values():
                cliente.send(json.dumps({'tipo': 'I', 'id_transacao': id_transacao}).encode('utf-8'))
            print(f"Nonce válido encontrado por {nome}: {nonce}")
        else:
            # Notificar o cliente que o nonce é inválido
            clientes[nome].send(json.dumps({'tipo': 'R', 'id_transacao': id_transacao}).encode('utf-8'))
    else:
        print("Transação não encontrada.")

def main():
    global transacoes
    # Inicializar transações para teste
    transacoes[1] = {'transacao': 'Transação 1', 'bits_zero': 4}
    transacoes[2] = {'transacao': 'Transação 2', 'bits_zero': 5}

    # Criar socket
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind((HOST, PORTA))
    servidor.listen(5)
    print(f"Servidor escutando em {HOST}:{PORTA}")

    while True:
        conn, addr = servidor.accept()
        threading.Thread(target=tratar_cliente, args=(conn, addr)).start()

if __name__ == "__main__":
    main()