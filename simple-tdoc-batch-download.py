
import threading
import requests
import wget
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import os
import queue
import time
import re

sleep_time = 10


class FileDownloader(threading.Thread):
    def __init__(self, url, save_path, qu, stop_event):
        super(FileDownloader, self).__init__()
        self.url = url
        self.save_path = save_path
        self.queue = qu
        self.download_successful = False
        self.message = ''
        self.stop_event = stop_event  # 暂时没用

    # #产生 stop event
    # def stop(self):
    #     self._stop_event.set()

    def run(self):
        try:
            thread_id = threading.get_ident()
            response = requests.get(self.url, stream=True)
            print(f"get connection response: {response}")

            response.raise_for_status()

            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                t = f"FileDownloader Thread : response[200], start downloading: {self.url.split('/')[-1]}, file size: {total_size}"
                self.queue.put(t)

                # Set the initial progress to 0
                progress = 0
                # Download the file in chunks and update the progress
                # the self.save_path here is only a dir, so it needs to add the zip filename(already added .zip )
                # with open(self.save_path + self.url.split('/')[-1] , 'wb') as file:
                with open(self.save_path, 'wb') as file:
                    response = requests.get(self.url, stream=True)
                    temp_percentage = 0
                    for data in response.iter_content(chunk_size=1024):
                        if self.stop_event.is_set():
                            e = "stop event is triggered."
                            print(f"FileDownloader Thread: Failed to download {self.url}: {e}")
                            # use << >> to include the file that failed.
                            self.queue.put(f"FileDownloader Thread: Failed to download <<{self.url}>>: {e}")
                            self.download_successful = False
                            self.message = f"Progress Count:FileDownloader Thread {thread_id}: <<1>>, Failed"
                            self.queue.put(self.message)
                            break
                        file.write(data)
                        progress += len(data)
                        percentage = (progress / total_size) * 100
                        # print(f"XXX Download progress: {percentage:.2f}%")            
                        if percentage - temp_percentage >= 0.5:
                            self.message = f"Progress Detail: <<{percentage:.2f}>>"
                            self.queue.put(self.message)
                            temp_percentage = percentage

                # # use wget method
                # ret = wget.download(self.url, self.save_path)
                # print(f'\n\tret: {ret}', f'{self.url.split("/")[-1]}')
                # if ret.split('/')[-1] == self.url.split('/')[-1]:
                #     print(f"\t{self.url.split('/')[-1]} is downloaded")
                #     self.message = f"FileDownloader Thread {thread_id}: {self.url.split('/')[-1]} is downloaded."
                # else:
                #     text1 = f"Warning: FileDownloader Thread: Download may fail, or file names are not the same:"
                #     print(f"\t{text1} {self.url.split('/')[-1]}")
                #     self.message = f"FileDownloader Thread {thread_id}: {text1} FileName is {self.url.split('/')[-1]}"

                # self.queue.put(self.message)

                self.message = f"Progress Count:FileDownloader Thread {thread_id}: <<1>>, Succeeded"
                self.queue.put(self.message)
                print(f"{self.url.split('/')[-1]} is downloaded, info from FileDownloader Thread.")
                self.download_successful = True

        except Exception as e:
            print(f"FileDownloader Thread: Failed to download {self.url}: {e}")
            # use << >> to include the file that failed.
            self.queue.put(f"{self.url.split('/')[-1]}: Failed to download \n<<{self.url}>>: {e}")
            self.download_successful = False
            self.message = f"Progress Count:FileDownloader Thread {thread_id}: <<1>>, Failed"
            self.queue.put(self.message)


# the main class
class FileDownloaderApp(tk.Frame):
    def __init__(self, master=None):
        super(FileDownloaderApp, self).__init__(master)        
        
        self.root = master
        self.root.withdraw()
        self.root.title("Baicells 3GPP TDocs Downloader")
        # self.root.configure(bg="lightgray")

        # # set progress bar
        self.style = ttk.Style()
        self.style.theme_use("clam")  
        self.style.configure("custom.Horizontal.TProgressbar", troughcolor="lightgray", background="green") 

        self.contents = ""  
        self.file_list = []
        self.file_urls = []
        self.save_path = ""
        self.downloader_list = []
        self.queue = queue.Queue()
        self.successful_downloads = []
        self.failed_downloads = []
        self.progress_file_count = 0
        self.progress_per_file = 0
        # self.progress_per_file_hold_flag = False
        self.stop_event = threading.Event()

        self.layout()
        self.set_screen()
        self.root.deiconify()

    def change_progress_bar_color(self, color):
        self.style.configure("custom.Horizontal.TProgressbar", background=color)

    def set_screen(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()        
        width, height = self.root.winfo_width(), self.root.winfo_height()
        x, y = (screen_width-width)/2, (screen_height-height)/2
        self.root.geometry(f"{width}x{height}+{int(x)}+{int(y)}")         
        
    def fit_window_size(self):
        # Update the window size to fit all components
        self.root.update()     
        self.root.resizable(0, 0)

    def check_n_load_from_txt(self):
        file_path = 'filenames.txt'
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                self.contents = file.read()
                # Process the contents here or print them, etc.
                print(self.contents)
                t = f"read filenames from filenames.txt."
                print(t)
                self.update_log(t)
        else:
            t = f"The file 'filenames.txt' does not exist, please copy filenames from TDoc list file."
            print(t)        
            self.update_log(t)

    def update_status_files_process(self, text):
        self.label_var_process_info.set(text)
        # self.log_text.insert("end", text + "\n")
        # self.log_text.see("end")  # Auto-scroll to the end

    def update_textbox_failed_files(self, text):
        self.textbox_failed_files.insert(tk.END, text + '\n')

    def clean_textbox_failed_files(self):
        self.textbox_failed_files.delete(1.0, tk.END)

    def on_text_insert(self, event):
        # the flag below is to prevent this function being called twice
        flag = self.textbox_filenames.edit_modified()
        if flag:
            self.current_line = self.textbox_filenames.index("insert").split(".")[0]
            print(f"line {self.current_line}")
            self.check_if_text_repeated("download_list")
            self.textbox_filenames.see(f"{self.current_line}.0")

            l = len(self.textbox_filenames.get("1.0", tk.END).strip().split("\n"))
            m = self.textbox_filenames.get("1.0", tk.END).strip().split("\n")
            print(f"self.textbox_filenames.get(): {m}")
            if l == 1 and m[0] == '':
                l = 0
            text = f"-- #{l} files are selected."
            # print(text)
            self.label_var1.set(text)
            self.update_log(text)
        self.textbox_filenames.edit_modified(False)  # Reset the modified flag for text widget!

    def update_label(self):
        try:
            message = self.queue.get(0)
            self.label_var_process_info.set(message)
            self.root.after(200, self.update_label)
        except queue.Empty:
            self.root.after(200, self.update_label)

    def update_log(self, message):
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")  # Auto-scroll to the end

    def process_message(self):
        try:
            # self.queue.get_nowait() will not block here
            message = self.queue.get_nowait()
            if "Progress Count" in message:
                match = re.search(r'<<([^"]*)>>', message)
                if match:
                    i = int(match.group(1))
                    print(i)
                    self.progress_file_count += i
                    self.progress_per_file=0
                    # self.progress_per_file_hold_flag = True
                    self.update_progress_bar() 
                    
            elif "Progress Detail" in message:
                self.log_text.insert("end", "+")
                self.log_text.see("end")
                match = re.search(r'<<([^"]*)>>', message)
                if match:
                    # if self.progress_per_file_hold_flag == False:
                    self.progress_per_file = float(match.group(1))
                    #!!! some work here to make the progress bar more smooth
                    # self.update_progress_bar() 
            else:
                self.update_log(message)
            # elif "response[200], start downloading" in message:
            #     self.progress_per_file_hold_flag = False
            #     self.update_log(message)

            if  "Failed to download" in message:
                match = re.search(r'<<([^"]*)>>', message)
                if match:
                    print(match.group(1))
                    t = match.group(1)
                    tt = t.split('/')[-1].replace(".zip","")
                    self.update_textbox_failed_files(tt)

                    self.failed_downloads.append(tt)
                    self.label_failed_info.set(f"#{len(self.failed_downloads)} downloads failed [ Processing message].")
                    # self.change_progress_bar_color("blue")
                    if len(self.failed_downloads) != 0:
                        self.change_progress_bar_color("red")               
                

        except queue.Empty:
            pass
        self.root.after(sleep_time, self.process_message)

    # main download thread
    def download_files(self, file_urls, save_path, my_queue, stop_event):
        self.process_message()
        for url in file_urls:
            try:
                self.update_log(f'\nMain Download Thread: Creating FileDownloader for {url.split("/")[-1]}')
                downloader = FileDownloader(url, f"{save_path}/{url.split('/')[-1]}", my_queue, stop_event)
                downloader.setDaemon(True)
                downloader.start()
                self.downloader_list.append(downloader)


                downloader.join()
                # self.update_label()
                
            except Exception as e:
                t = f"Main Download Thread: Exception for {url}: {e}"
                print(t)
                self.update_log(t)
                # self.failed_downloads.append(url)
                # self.update_status_files_process(text=f"Download Thread: Failed to download {url.split('/')[-1]}")
                t = url.split('/')[-1].replace(".zip", "")
                self.update_textbox_failed_files(t)

        # Wait for all threads to finish
        # ----------just for test---------------
        print(f"## threading.active_count(): {threading.active_count()}") #?
        num = threading.active_count()
        print(f"active thread num before close: {num}")
        active_threads = threading.enumerate()
        # Print the details of active threads
        for thread in active_threads:
            print(f"Thread name: {thread.name}, Thread ID: {thread.ident}")
        # -------------------------

        sum_count = 0
        # for downloader in threading.enumerate():
        for downloader in self.downloader_list:            
            if isinstance(downloader, FileDownloader):
                temp_url = downloader.url
                if downloader.download_successful:
                    #-------------------------
                    # collect successful_downloads
                    self.successful_downloads.append(temp_url)
                    print(f"### {temp_url}: len(self.successful_downloads) increased to : {len(self.successful_downloads)}")
                    tt = f"Download Thread: {temp_url.split('/')[-1]} downloaded successfully."
                    self.update_log(tt)
                    # self.update_status_files_process(tt)
                else:
                    tt = f"Download Thread: Fail downloading {temp_url.split('/')[-1]}"
                    
                    print(f"### {temp_url}: len(self.failed_downloads) increased to: {len(self.failed_downloads)}")
                    # self.update_status_files_process(tt)
                    self.update_log(tt)
                    # # remove .zip
                    # t = downloader.url.split('/')[-1].replace(".zip", "")
                    # self.update_textbox_failed_files(t)
            else:
                sum_count += 1
                print(f"not a FileDownloader object count: {sum_count}.")
        
        # [summary part]
        time.sleep((sleep_time+100)/1000)
        self.summary()
        self.button_download.config(state="normal")

        # self.log_text.yview_moveto(1)

        # !!! to improve here, add automatic re-downloading failed files
        # automatically download failed files
        # if len(self.failed_downloads) > 0:
        #     # retry = input(f"Failed to download {len(self.failed_downloads)} files. Retry? (y/n)")
        #     # if retry.lower() == "y":
        #     self.textbox_filenames.delete("1.0", "end")
        #     self.textbox_filenames.insert("end", "\n".join(self.failed_downloads))
        #     self.update_status_files_process(text=f"re-download failed files...")
        #     self.failed_downloads = []
        #     self.clean_textbox_failed_files()
        #     self.start_download()

    # This function will trigger another function self.download_files() to start.

    def summary(self):
        t = f"{len(self.file_urls)} files are selected."
        text = f"#{len(self.file_urls)} files selected, " \
                f"#{len(self.successful_downloads)} files downloaded successful [Summary]."
                #    f"#{len(self.file_urls)-len(self.failed_downloads)} files downloaded successful."
        self.label_var1.set(text)
        self.update_status_files_process(text)
        self.update_log(text)

        if len(self.failed_downloads) != 0:
            self.change_progress_bar_color("red")
        t_fail = f"#{len(self.failed_downloads)} downloads failed  [Summary]."
        self.label_failed_info.set(t_fail)
        self.update_log(t_fail)

        if len(self.failed_downloads) + len(self.successful_downloads) != len(self.file_urls):
            self.update_log("wrong math! line 228")
            self.update_log(f"{len(self.file_urls)}?= #{len(self.successful_downloads)}+{len(self.failed_downloads)}")
        
        self.check_if_text_repeated("fail_list")

    def clean_state(self):
        self.progress_file_count = 0
        self.progress_per_file = 0
        
        self.file_list = []
        self.successful_downloads = []
        self.failed_downloads = []
        self.downloader_list = []
        self.textbox_failed_files.delete("1.0", "end")
        self.label_failed_info.set("-- Number of Files failed.")
        

    def start_download(self):
        self.button_download.config(state="disabled")
        self.change_progress_bar_color("green")
        # clean
        self.clean_state()
        # start
        self.file_list = self.textbox_filenames.get("1.0", tk.END).strip().split("\n")
        #  URL + filename +.zip 
        self.file_urls = [f"{self.textbox_url.get()}/{filename}.zip" for filename in self.file_list]
        print("files are: ")
        for url in self.file_urls:
            print(url)
        self.save_path = self.textbox_savepath.get()
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)
            t = f"Creating save path dir."
            print(t)
            self.update_log(t)
        else:
            t = f"save path already exists, start downloading..."
            print(t)
            self.update_log(t)
        
        t = f"-- # {len(self.file_urls)} files are selected. [Start downloading...]"
        print(t)
        self.update_log(t)
        self.label_var1.set(t) 
        self.update_log("Start downloading zip files")

        self.update_progress_bar()

        download_thread = threading.Thread(target=self.download_files,
                                           args=(self.file_urls, self.save_path, self.queue, self.stop_event))
        download_thread.setDaemon(True)
        download_thread.start()

        print("start download button process finished.")

    def update_progress_bar(self):
        # !!! to do show the current progress more smoothly
        current_progress = self.progress_file_count/len(self.file_urls) *100 
        # current_progress = self.progress_file_count/len(self.file_urls) *100 + self.progress_per_file/len(self.file_urls)
        if self.progress_file_count == len(self.file_urls):
            self.progress_var.set(100)
            self.label_var_process_info.set("Download complete!")
        if current_progress < 100:
            self.progress_var.set(current_progress)
            self.label_var_process_info.set(f"Progress: {current_progress:.2f}%   #{self.progress_file_count} Files proceeded." )
            root.after(50, self.update_progress_bar)  


    def check_if_text_repeated(self, where):
        if where == "fail_list":
            # check whether the failed filename list are repeated.
            failed_text = self.textbox_failed_files.get("1.0",tk.END)
            names = failed_text.strip().split("\n")
            # Check for duplicates
            unique_names = []
            for name in names:
                if name not in unique_names and name != "" :
                        unique_names.append(name)
                else:
                    self.update_log("detected repeated filenames in textbox_failed")
            fail_text = '\n'.join(unique_names)
            self.textbox_failed_files.delete("1.0", tk.END)
            self.textbox_failed_files.insert(tk.END, fail_text)

        elif where == "download_list":
            # check whether the failed filename list are repeated.
            dl_text = self.textbox_filenames.get("1.0",tk.END)
            names = dl_text.strip().split("\n")
            # Check for duplicates
            unique_names = []
            print(len(names))
            for name in names:
                print(f"name : {name}")
                if name not in unique_names:
                    if name !='':
                        unique_names.append(name)
                else:
                    self.update_log(f"detected repeated filenames in textbox_download_list: {name}")                    
            filenames_text = '\n'.join(unique_names)
            self.textbox_filenames.delete("1.0", tk.END)
            self.textbox_filenames.insert(tk.END, filenames_text)


    # !!! to improve the close button func
    def close_program(self):
        self.stop_event.set()

        time.sleep((sleep_time+100)/1000)

        num = threading.active_count()
        active_threads = threading.enumerate()
        print(f"active thread num before close: {num}")
        # Print the details of active threads
        for thread in active_threads:
            print(f"Thread name: {thread.name}, Thread ID: {thread.ident}")    

        # # Wait for all threads to finish
        # for downloader in self.downloader_list:
        #     if isinstance(downloader, FileDownloader):
        #         print("Stop call. this is a FileDownloader object.")
        #         downloader.stop()
        #     else:
        #         print("Stop call ERROR: this is NOT FileDownloader object.")

        # for downloader in self.downloader_list:
        #     if isinstance(downloader, FileDownloader):
        #         downloader.join()
        #         print("this is a FileDownloader object.")
        #     else:
        #         print("this is NOT FileDownloader object.")

        self.root.destroy()

    # layout the UI
    def layout(self):
        # Step1. website URL label
        self.label_url = tk.Label(self.root, text="Step①. Specify URL ↓", font=("Arial", 12, "bold"))
        self.label_url.grid(row=0, column=0, padx=5, pady=1, sticky='w')


        # 1a. website URL
        self.textbox_url = tk.Entry(self.root, width=55, font=("Arial", 12))
        self.textbox_url.grid(row=1, column=0, columnspan=3, padx=5, pady=1, sticky='w')
        self.textbox_url.insert("end", "https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_113/Docs")
        
        # Step2. save path
        self.label_savepath = tk.Label(self.root, text="Step②. Set save path ↓", font=("Arial", 12, "bold"))
        self.label_savepath.grid(row=2, column=0, columnspan=3, padx=5, pady=1, sticky='w')
        self.textbox_savepath = tk.Entry(self.root, width=55, font=("Arial", 12))
        self.textbox_savepath.grid(row=3, column=0, columnspan=2, padx=5, pady=1, sticky='w')
        self.textbox_savepath.insert("end", "./Tdocs_download_dir")

        # Step3. filenames
        self.label1 = tk.Label(self.root, text="Step③. Enter file names ↓", font=("Arial", 12, "bold"))
        self.label1.grid(row=5, column=0, columnspan=2, padx=5, pady=0, sticky='nw')
        self.label1a = tk.Label(self.root, text="*Note: Use 'enter' to separate filenames.")
        self.label1a.grid(row=6, column=0, columnspan=2, padx=5, pady=0, sticky='nw')

        # still step3, file names to be downloaded
        self.textbox_filenames = ScrolledText(self.root, height=7, width=13, wrap=tk.WORD, font=("Arial", 12))
        self.textbox_filenames.grid(row=7, column=0, padx=5, pady=1, sticky='nw')
        # self.textbox_filenames.insert("end", "R1-2305660"+'\n'+"R1-2305896")

        # 4. failed file names  Row 0
        self.status_label_files_failed = tk.Label(self.root, text="Failed files:    ",
                                                  font=("Arial", 12, "bold"))
        self.status_label_files_failed.grid(row=6, column=1, padx=5, pady=1, sticky='ne')

        self.textbox_failed_files = ScrolledText(self.root, height=7, width=13, wrap=tk.WORD,
                                                 bg="lightgray", font=("Arial", 12))
        self.textbox_failed_files.grid(row=7, column=1, padx=5, pady=1, sticky='ne')
        self.textbox_failed_files.insert("end", "")

        # 4. button for download
        self.button_download = tk.Button(self.root, text="Step④. Download", fg="#3B3BFF",
                                         font=("Arial", 12, "bold"), width=15,
                                         command=self.start_download)
        self.button_download.grid(row=8, column=0, padx=5, pady=1, sticky='w')
        # 5. button for close
        self.button_close = tk.Button(self.root, text="Close window", width=13, command=self.close_program)
        self.button_close.grid(row=14, column=1, padx=15, pady=1, sticky='ne')

        # status label 1 -- number of files
        self.label_var1 = tk.StringVar()
        self.label_var1.set("-- Number of files in total.")
        self.status_label1 = tk.Label(self.root, textvariable=self.label_var1,
                                      fg="#316262", font=("Arial", 10, "bold"))
        self.status_label1.grid(row=9, column=0, columnspan=2, padx=5, pady=1, sticky='w')

        # progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(root, variable=self.progress_var, length=480, maximum=100, style="custom.Horizontal.TProgressbar")    
        self.progress_bar.grid(row=10, column=0, columnspan=2, padx=5, pady=1, sticky='w')

        # status label 3 -- download files process info
        self.label_var_process_info = tk.StringVar()
        self.label_var_process_info.set("-- Process Info.")
        self.status_label_files_process = tk.Label(self.root, textvariable=self.label_var_process_info,
                                                   fg="#316262", font=("Arial", 10, "bold"))
        self.status_label_files_process.grid(row=11, column=0, columnspan=2, padx=5, pady=1, sticky='nw')

        # # status label 2 -- number of files download succeeded
        # self.label_var2 = tk.StringVar()
        # self.label_var2.set("-- Number of files succeeded.")
        # self.status_label_sum = tk.Label(self.root, textvariable=self.label_var2,
        #                                  fg="#316262", font=("Arial", 10, "bold"))
        # self.status_label_sum.grid(row=11, column=0, columnspan=2, padx=5, pady=1, sticky='nw')


        # status label 4 -- number of download files failed
        self.label_failed_info = tk.StringVar()
        self.label_failed_info.set("-- Number of Files failed.")

        self.status_label_files_failed = tk.Label(self.root, textvariable=self.label_failed_info,
                                                  fg="#316262", font=("Arial", 10, "bold"))
        self.status_label_files_failed.grid(row=12, column=0, columnspan=2, padx=5, pady=1, sticky='nw')

        # column for Log info
        self.label_info = tk.Label(root, text="Log information↓", font=("Arial", 12, "bold"))
        self.label_info.grid(row=14, column=0, columnspan=2, padx=5, pady=1, sticky='w')

        # self.log_text = tk.Text(root, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text = ScrolledText(root, width=78, height=15, wrap=tk.WORD,
                                     font=("Arial", 8, "bold"), fg="#316262", bg="lightgray")
        self.log_text.grid(row=15, column=0, columnspan=3,  padx=5, pady=1, sticky='w')
        # self.log_text.grid(row=12, column=1, rowspan=5, columnspan=2,  padx=5, pady=1, sticky='en')

        self.label_auth = tk.Label(self.root, text="Initial Version, BUGs guaranteed!\t   Baicells Technologies Co.Ltd \tAuthor: Wxn 2023.7", font=("Arial", 10))
        self.label_auth.grid(row=16, column=0, columnspan=3, padx=5, pady=1,sticky='w')

        self.root.columnconfigure(0, minsize=15)
        self.root.columnconfigure(1, minsize=10)
        self.root.columnconfigure(2, minsize=0)

        self.check_n_load_from_txt()
        self.fit_window_size()

        # Bind the text insertion event to the custom function
        # self.textbox_filenames.bind("<<TextInsert>>", self.on_text_insert)
        self.textbox_filenames.bind("<<Modified>>", self.on_text_insert)
        self.textbox_filenames.insert("end", self.contents)


if __name__ == "__main__":
    root = tk.Tk()
    app = FileDownloaderApp(master=root)
    app.mainloop()



