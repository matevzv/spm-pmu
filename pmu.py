import socketserver

from queue import Queue
from threading import Thread
from threading import Lock
from synchrophasor.frame import *
from datetime import datetime

class Service(socketserver.BaseRequestHandler):
    queue = None
    sending_measurements_enabled = False
    header = None
    cfg2 = None
    socket_open = True

    def __init__(self, request, client_address, server):
        self.queue = server.queue
        self.header = server.header
        self.cfg2 = server.cfg2
        socketserver.BaseRequestHandler.__init__(self, request, client_address, server)

    def get_time(self):
        dt = datetime.now()
        return [int(dt.timestamp()), dt.microsecond]

    def pmu_handler(self, received_data):
        command = None
        response = b''

        received_message = CommonFrame.convert2frame(received_data)
        command = received_message.get_command()
        print("Client " + str(self.client_address) + " command " + command)

        if command == 'start':
            self.sending_measurements_enabled = True

        elif command == 'stop':
            self.sending_measurements_enabled = False

        elif command == 'header':
            time = self.get_time()
            self.header.set_time(time[0], time[1])
            response = self.header.convert2bytes()

        elif command == 'cfg2':
            time = self.get_time()
            self.cfg2.set_time(time[0], time[1])
            response = self.cfg2.convert2bytes()

        return response

    def handle(self):
        print("Client connected with " + str(self.client_address))

        lock = Lock()

        t = Thread(target = self.send_data, args=[])
        t.start()

        while True:
            try:
                data = self.request.recv(1024)
                if len(data) == 0:
                    break
            except:
                break

            try:
                byts = self.pmu_handler(data)
                with lock:
                    self.request.sendall(byts)
            except:
                continue

        self.socket_open = False
        t.join()
        print("Client exited with " + str(self.client_address))

    def send_data(self):
        while self.socket_open:
            send_data = self.queue.get()
            if self.sending_measurements_enabled == True:
                try:
                    self.request.sendall(send_data)
                except:
                    continue
                finally:
                    self.queue.task_done()

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
        print("PMU with ID " + str(pmu_id) + " started on " + ip + ":" + str(port))
        self.pmu_id = pmu_id
        self.num_pmu = cfg2.num_pmu
        self.data_format = cfg2.data_format
        socketserver.TCPServer.allow_reuse_address = True
        server = ThreadedTCPServer((ip, port), Service, queue=self.queue)
        server.header = header
        server.cfg2 = cfg2
        Thread(target = server.serve_forever, args=[]).start()

    def send_data(self, phasors=[], analog=[], digital=[], freq=0, dfreq=0,
                stat=('ok', True, 'timestamp', False, False, False, 0, '<10', 0),
                soc=None, frasec=None):

        data_frame = DataFrame(self.pmu_id, stat, phasors, freq, dfreq, analog, digital,
                            self.data_format, self.num_pmu)

        data_frame.set_time(soc, frasec)
        self.queue.put_nowait(data_frame.convert2bytes())
