import os

os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import cv2
import pyvirtualcam
import subprocess
import time
import threading
import json

CONFIG_FILE = "config_webcam.json"


class CapturaSemAtraso:

    def __init__(self, url):
        self.cap = cv2.VideoCapture(url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.ret = False
        self.frame = None
        self.rodando = False
        self.thread = None

        if self.cap.isOpened():
            self.ret, self.frame = self.cap.read()
            self.rodando = True
            self.thread = threading.Thread(target=self._atualizar, daemon=True)
            self.thread.start()

    def _atualizar(self):
        while self.rodando:
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    self.ret = ret
                    self.frame = frame
                else:
                    self.ret = False
            else:
                time.sleep(0.01)

        if self.cap and self.cap.isOpened():
            self.cap.release()

    def read(self):
        return self.ret, self.frame

    def isOpened(self):
        return self.cap.isOpened() if self.cap else False

    def get(self, propId):
        return self.cap.get(propId)

    def release(self):
        self.rodando = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)


class WebcamApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Webcam USB/WiFi")
        self.root.geometry("380x520")
        self.root.resizable(False, False)
        self.root.eval('tk::PlaceWindow . center')

        self.is_running = False
        self.video_thread = None
        self.preview_frame = None
        self.porta_padrao = "8080"
        self.url_atual = ""

        self.modo_conexao = tk.StringVar(value="USB")
        self.fps_var = tk.StringVar(value="30")

        self.lbl_titulo = tk.Label(root, text="Painel da Webcam", font=("Helvetica", 14, "bold"))
        self.lbl_titulo.pack(pady=(15, 5))

        frame_conexao = tk.Frame(root)
        frame_conexao.pack(pady=5)

        tk.Radiobutton(frame_conexao, text="Cabo USB (ADB)", variable=self.modo_conexao, value="USB",
                       command=self.mudar_modo).grid(row=0, column=0, padx=10)
        tk.Radiobutton(frame_conexao, text="Rede Wi-Fi", variable=self.modo_conexao, value="WIFI",
                       command=self.mudar_modo).grid(row=0, column=1, padx=10)

        self.frame_configs = tk.Frame(root)
        self.frame_configs.pack(pady=5)

        tk.Label(self.frame_configs, text="IP do Celular:").grid(row=0, column=0, sticky="e")
        self.entry_ip = tk.Entry(self.frame_configs, width=15)
        self.entry_ip.insert(0, "192.168.0.")
        self.entry_ip.grid(row=0, column=1, padx=5, pady=2)

        tk.Label(self.frame_configs, text="FPS Desejado:").grid(row=1, column=0, sticky="e")
        self.combo_fps = ttk.Combobox(self.frame_configs, textvariable=self.fps_var, values=["15", "24", "30", "60"],
                                      width=12, state="readonly")
        self.combo_fps.grid(row=1, column=1, padx=5, pady=2)
        self.combo_fps.bind("<<ComboboxSelected>>", lambda e: self.salvar_configuracoes())

        self.frame_preview = tk.Frame(root, width=320, height=180, bg="#222222")
        self.frame_preview.pack(pady=15)
        self.frame_preview.pack_propagate(False)

        self.lbl_preview = tk.Label(self.frame_preview, text="[ Câmera Desligada ]", bg="#222222", fg="white")
        self.lbl_preview.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        self.lbl_status = tk.Label(root, text="Status: Desconectado", font=("Helvetica", 10), fg="gray")
        self.lbl_status.pack(pady=(0, 10))

        self.btn_iniciar = tk.Button(root, text="▶ Iniciar Câmera", font=("Helvetica", 11), bg="#4CAF50", fg="white",
                                     width=20, command=self.iniciar_camera)
        self.btn_iniciar.pack(pady=5)

        self.btn_parar = tk.Button(root, text="■ Parar Câmera", font=("Helvetica", 11), bg="#F44336", fg="white",
                                   width=20, state=tk.DISABLED, command=self.parar_camera)
        self.btn_parar.pack(pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.ao_fechar_janela)

        self.carregar_configuracoes()
        self.atualizar_interface_preview()

    def salvar_configuracoes(self):
        config = {
            "modo": self.modo_conexao.get(),
            "ip": self.entry_ip.get(),
            "fps": self.fps_var.get()
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            print(f"Erro ao salvar configurações: {e}")

    def carregar_configuracoes(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.modo_conexao.set(config.get("modo", "USB"))
                    self.fps_var.set(config.get("fps", "30"))

                    self.entry_ip.config(state=tk.NORMAL)
                    self.entry_ip.delete(0, tk.END)
                    self.entry_ip.insert(0, config.get("ip", "192.168.0."))
            except Exception as e:
                print(f"Erro ao carregar configurações: {e}")

        self.mudar_modo()

    def mudar_modo(self):
        if self.modo_conexao.get() == "WIFI":
            self.entry_ip.config(state=tk.NORMAL)
        else:
            self.entry_ip.config(state=tk.DISABLED)

        self.salvar_configuracoes()

    def atualizar_status(self, mensagem, cor):
        self.lbl_status.config(text=mensagem, fg=cor)
        self.root.update_idletasks()

    def atualizar_interface_preview(self):
        if self.is_running and self.preview_frame is not None:
            frame_rgb = cv2.cvtColor(self.preview_frame, cv2.COLOR_BGR2RGB)

            img = Image.fromarray(frame_rgb)
            img.thumbnail((320, 180))

            imgtk = ImageTk.PhotoImage(image=img)

            self.lbl_preview.imgtk = imgtk
            self.lbl_preview.configure(image=imgtk, text="")

        elif not self.is_running:
            self.lbl_preview.config(image='', text="[ Câmera Desligada ]")

        self.root.after(30, self.atualizar_interface_preview)

    def executar_adb(self, comandos):
        return subprocess.run(comandos, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)

    def configurar_adb(self):
        self.atualizar_status("Configurando USB...", "orange")
        try:
            self.executar_adb(["adb", "forward", f"tcp:{self.porta_padrao}", f"tcp:{self.porta_padrao}"])
            return True
        except Exception:
            messagebox.showerror("Erro ADB",
                                 "Não foi possível configurar a porta USB. O celular está conectado com Depuração ativada?")
            return False

    def iniciar_camera(self):
        self.salvar_configuracoes()
        modo = self.modo_conexao.get()

        if modo == "USB":
            if not self.configurar_adb():
                self.atualizar_status("Status: Erro de Conexão USB", "red")
                return
            self.url_atual = f"http://127.0.0.1:{self.porta_padrao}/video"
        else:
            ip_digitado = self.entry_ip.get().strip()
            if not ip_digitado:
                messagebox.showwarning("Aviso", "Por favor, digite o IP do celular.")
                return
            self.url_atual = f"http://{ip_digitado}:{self.porta_padrao}/video"

        self.is_running = True
        self.btn_iniciar.config(state=tk.DISABLED)
        self.btn_parar.config(state=tk.NORMAL)
        self.combo_fps.config(state=tk.DISABLED)
        self.mudar_modo()

        for child in self.frame_configs.winfo_children():
            if isinstance(child, tk.Entry) or isinstance(child, ttk.Combobox):
                child.configure(state='disable')

        self.atualizar_status(f"Conectando via {modo}...", "blue")

        self.video_thread = threading.Thread(target=self.loop_video, daemon=True)
        self.video_thread.start()

    def parar_camera(self):
        self.is_running = False
        self.preview_frame = None
        self.btn_parar.config(state=tk.DISABLED)
        self.atualizar_status("Encerrando...", "orange")

    def loop_video(self):
        try:
            while self.is_running:
                cap = CapturaSemAtraso(self.url_atual)

                if not cap.isOpened():
                    time.sleep(1)
                    continue

                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps_escolhido = int(self.fps_var.get())

                self.atualizar_status(f"Conectado ({width}x{height} - {fps_escolhido} FPS)", "green")

                try:
                    with pyvirtualcam.Camera(width, height, fps_escolhido, fmt=pyvirtualcam.PixelFormat.BGR) as cam:
                        while self.is_running:
                            ret, frame = cap.read()

                            if not ret or frame is None:
                                self.atualizar_status("Sinal interrompido...", "orange")
                                self.preview_frame = None
                                break

                            self.preview_frame = frame.copy()

                            cam.send(frame)
                            cam.sleep_until_next_frame()

                except Exception as e:
                    print(f"Erro na câmera virtual: {e}")
                finally:
                    cap.release()
                    time.sleep(1)

        finally:
            if self.modo_conexao.get() == "USB":
                self.executar_adb(["adb", "forward", "--remove", f"tcp:{self.porta_padrao}"])

            if self.root.winfo_exists():
                self.atualizar_status("Status: Desconectado", "gray")
                self.btn_iniciar.config(state=tk.NORMAL)
                self.btn_parar.config(state=tk.DISABLED)
                self.combo_fps.config(state="readonly")

                self.mudar_modo()

    def ao_fechar_janela(self):
        self.salvar_configuracoes()

        if self.is_running:
            self.is_running = False
            self.atualizar_status("Fechando...", "red")
            self.root.update()
            time.sleep(1)

        self.executar_adb(["adb", "forward", "--remove", f"tcp:{self.porta_padrao}"])
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = WebcamApp(root)
    root.mainloop()
