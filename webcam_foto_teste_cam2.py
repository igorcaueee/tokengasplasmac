import cv2

# Caminho do dispositivo da câmera
camera_path = '/dev/video4'  # Altere para o caminho correto de sua câmera
cap = cv2.VideoCapture(camera_path)

# Verifique se a câmera foi aberta corretamente
if not cap.isOpened():
    print(f"Erro ao acessar a câmera: {camera_path}")
    exit()

# Captura o quadro da câmera
ret, frame = cap.read()

# Se o quadro foi capturado corretamente
if ret:
    # Salva a imagem em um arquivo
    cv2.imwrite("foto_capturada_2.jpg", frame)
    print("Imagem salva como 'foto_capturada_2.jpg'")
else:
    print("Erro ao capturar imagem")

# Libera a câmera
cap.release()
