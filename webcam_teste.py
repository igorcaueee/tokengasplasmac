import cv2

# Conectar à primeira câmera (ID 0)
camera_id = "/dev/video0"  # Você pode alterar para 1, 2, etc. se estiver conectando mais de uma câmera
cap = cv2.VideoCapture(camera_id)

# Verifique se a câmera foi aberta corretamente
if not cap.isOpened():
    print("Erro ao acessar a câmera")
    exit()

while True:
    # Captura o quadro da câmera
    ret, frame = cap.read()

    # Se o quadro foi capturado corretamente
    if ret:
        # Exibe o quadro na janela
        cv2.imshow(f'Câmera {camera_id}', frame)
    
    # Encerra a visualização ao pressionar a tecla 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Libera a câmera e fecha as janelas
cap.release()
cv2.destroyAllWindows()
