import socketserver

from queue import Queue
from threading import Thread
from synchrophasor.frame import *
from datetime import datetime

class Service(socketserver.BaseRequestHandler):
    queue = None
    queues = None
    header = None
    cfg2 = None
    socket_open = True
    sending_measurements_enabled = False
    client_limit = 10

    def __init__(self, request, client_address, server):
        self.queue = Queue()
        self.queues = server.queues
        self.header = server.header
        self.cfg2 = server.cfg2
        socketserver.BaseRequestHandler.__init__(self, request, client_address, server)

    def get_time(self):
        dt = datetime.now()
        return [int(dt.timestamp()), dt.microsecond]

    def pmu_handler(self, received_data):
        command = None

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
            self.queue.put_nowait(['command', response])

        elif command == 'cfg2':
            time = self.get_time()
            self.cfg2.set_time(time[0], time[1])
            response = self.cfg2.convert2bytes()
            self.queue.put_nowait(['command', response])

    def handle(self):
        print("Client connected with " + str(self.client_address))

        if len(self.queues) < self.client_limit:
            self.queues.append(self.queue)
        else:
            print("Client limit exceeded: " + str(self.client_limit))
            print("Client exited with " + str(self.client_address))
            return

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
                self.pmu_handler(data)
            except:
                continue

        self.queues.remove(self.queue)
        self.socket_open = False
        self.queue.put(None)
        t.join()

        print("Client exited with " + str(self.client_address))

    def send_data(self):
        while self.socket_open:
            send_data = self.queue.get()
            try:
                if not isinstance(send_data, list):
                    if self.sending_measurements_enabled == False or send_data == None:
                        continue
                elif send_data[0] != 'command':
                    continue
                else:
                    send_data = send_data[1]

                self.request.sendall(send_data)
            except:
                continue
            finally:
                self.queue.task_done()

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True,
                 queues=None):
        self.queues = queues
        socketserver.TCPServer.__init__(self, server_address, Service,
                                        bind_and_activate=bind_and_activate)

class Pmu():
    queues = []
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
        server = ThreadedTCPServer((ip, port), Service, queues=self.queues)
        server.header = header
        server.cfg2 = cfg2
        Thread(target = server.serve_forever, args=[]).start()

    def send_data(self, phasors=[], analog=[], digital=[], freq=0, dfreq=0,
                stat=('ok', True, 'timestamp', False, False, False, 0, '<10', 0),
                soc=None, frasec=None):

        data_frame = DataFrame(self.pmu_id, stat, phasors, freq, dfreq, analog, digital,
                            self.data_format, self.num_pmu)

        data_frame.set_time(soc, frasec)
        for q in self.queues:
            q.put_nowait(data_frame.convert2bytes())
