import socketserver

from time import sleep
from threading import Thread
from multiprocessing import Queue
from synchrophasor.frame import *
from datetime import datetime

class Service(socketserver.BaseRequestHandler):
    queue = None
    sending_measurements_enabled = False
    header = None
    cfg2 = None

    def __init__(self, request, client_address, server):
        self.queue = server.queue
        self.header = server.header
        self.cfg2 = server.cfg2
        self.cfg2.set_id_code(server.pmu_id)
        socketserver.BaseRequestHandler.__init__(self, request, client_address, server)

    def pmu_handler(self, received_data):

        command = None
        response = None

        if len(received_data) > 0:
            received_message = CommonFrame.convert2frame(received_data)
            command = received_message.get_command()
            print(command)

            if command == 'start':
                self.queue.put(None)
                self.sending_measurements_enabled = True

            elif command == 'stop':
                self.queue.put(None)
                self.sending_measurements_enabled = False

            elif command == 'header':
                dt = datetime.now()
                self.header.set_time(int(dt.timestamp()), dt.microsecond)
                response = self.header.convert2bytes()
                self.queue.put(response)

            elif command == 'cfg1':
                self.queue.put(None)

            elif command == 'cfg2':
                dt = datetime.now()
                self.cfg2.set_time(int(dt.timestamp()), dt.microsecond)
                response = self.cfg2.convert2bytes()
                self.queue.put(response)

            elif command == 'cfg3':
                self.queue.put(None)

    def handle(self):
        data = 'init'
        print("Client connected with " + str(self.client_address))

        t = Thread(target = self.send_data, args=[])
        t.start()

        while True:
            try:
                data = self.request.recv(1024)
            except:
                self.queue.put('exit')
                break
            if len(data) == 0:
                self.queue.put('exit')
                break
            try:
                self.pmu_handler(data)
            except:
                continue

        t.join()
        print("Client exited")

    def send_data(self):
        while True:
            send_data = self.queue.get()
            if send_data is not None:
                if send_data == 'exit':
                    break
                elif isinstance(send_data, list) and send_data[0] == 'measurement':
                    if self.sending_measurements_enabled == True:
                        send_data = send_data[1]
                    else:
                        continue
            else:
                continue
            try:
                self.request.sendall(send_data)
            except:
                continue

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True,
                 queue=None):
        self.queue = queue
        socketserver.TCPServer.__init__(self, server_address, Service,
                                        bind_and_activate=bind_and_activate)

class Pmu():
    queue = Queue()
    pmu_id = None
    header = None
    cfg2 = None
    data_format = None
    num_pmu = None

    def __init__(self, header, cfg2, ip='', port=4712, pmu_id=1410):
        self.pmu_id = pmu_id
        self.num_pmu = cfg2.num_pmu
        self.data_format = cfg2.data_format
        server = ThreadedTCPServer((ip, port), Service, queue=self.queue)
        server.pmu_id = pmu_id
        server.header = header
        server.cfg2 = cfg2
        Thread(target = server.serve_forever, args=[]).start()

    def send_data(self, phasors=[], analog=[], digital=[], freq=0, dfreq=0,
                        stat=('ok', True, 'timestamp', False, False, False, 0, '<10', 0), soc=None, frasec=None):

        data_frame = DataFrame(self.pmu_id, stat, phasors, freq, dfreq, analog, digital,
                            self.data_format, self.num_pmu)

        data_frame.set_time(soc, frasec)
        self.queue.put(['measurement', data_frame.convert2bytes()])
