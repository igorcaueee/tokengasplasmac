import cv2

def detect():
    index=0
    arr=[]
    while True:
        cap = cv2.VideoCapture(index)
        if not cap.read()[0]:
            break
        else:
            print("Camera", index)
        cap.release()
        index=+1
    return arr

cameras = detect()
