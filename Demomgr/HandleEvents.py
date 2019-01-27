'''Classes designed to ease up the handling of a _events.txt file as written by the source engine'''
'''UNDER DEVELOPMENT, THESE DO NOT WORK AND ARE AS OF NOW UNUSED.'''

import re

_DEF = {	"sep":">\n", "resethandle":True}

read_DEF = {"blocksz":65536}

class Datachunk:
        def __init__(self, content, messagestruct, fromfile):
                self.content = content
                self.message = messagestruct
                self.fromfile = fromfile

        def __repr__(self):
                return self.content

        def __str__(self):
                return self.content

class EventDecodeError(BaseException):
	pass

class EventReader:
        def __init__(self, handle, cnf = {}, **cnfargs):

                if type(handle) is str:
                	handle = open(handle, "r")
                self.handle = handle
                self.cnf = _DEF
                self.cnf.update(read_DEF)
                self.cnf.update(cnfargs)
                self.cnf.update(cnf)

                if self.cnf["resethandle"]:
                	self.handle.seek(0)

                self.lastchunk = ""

                self.chunkbuffer = []

        def __enter__(self):
                return self

        def __exit__(self, *_):
                self.destroy()

        def __next__(self):
                return self.getchunks(1)

        def getchunks(self, toget = 1):
                '''Method that returns the number of specified datachunks in the file.'''
                while len(self.chunkbuffer) <= toget:
                        self.__read(1)
                returnbfr = []
                for _ in range(toget):
                        returnbfr.append(self.chunkbuffer.pop(0))
                return returnbfr

        def reset(self):
                '''Resets the EventReader to the start of the file.'''
                self.handle.seek(0)
                self.lastchunk = ""
                self.chunkbuffer = []

        def __read(self, itrs = 1):#ISSUE:Keeps returning the last chunk when hitting file end
                '''Internal method reading datachunks and adding them to self.chunkbuffer'''
                raw = ""
                rawread = ""
                logchunks = []
                done = False
                for _ in range(itrs):
                        if done: break
                        rawread = self.handle.read(self.cnf["blocksz"])
                        if rawread == "": #we can be sure the file is over.
                                done = True
                        raw = self.lastchunk + rawread
                        logchunks = raw.split(_DEF["sep"])
                        #Alright, so what can happen?
                        #A: The length of logchunks is 1
                                #Either that is one big logchunk or the last one, if rawread == ""
                        #B: The length of logchunks is 0
                                #This should not happen, unless the file is empty. Return empty list.
                        #C: The length of logchunks is >1
                                #That's nice, stuff buffer and save last to self.lastchunk
                        if len(logchunks) == 0:
                                self.chunkbuffer = self.chunkbuffer + Datachunk("",{"last":True},self.handle.name)
                                break
                        elif len(logchunks) == 1:
                                if rawread == "":
                                        self.lastchunk = ""
                                        pass#self.lastchunk is a valid chunk -> pass is ok!
                                else:
                                        self.lastchunk = logchunks.pop(0)
                                        continue
                        else:
                                self.lastchunk = logchunks.pop(-1)
                        self.chunkbuffer = self.chunkbuffer + [Datachunk(i, {"last":bool(rawread)}, self.handle.name) for i in logchunks]

        def close(self):
                self.destroy()

        def destroy(self):
                self.handle.close()
                del self

if __name__ == "__main__":
	#_TESTPAT = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\team fortress 2\\tf\\prec_demos\\_events.txt"
	_TESTPAT = "/media/pi/EGG/Code/python/_events.txt"
	with EventReader(_TESTPAT, blocksz = 65536) as rdr:
                while True:
                        inp = input()
                        if inp == "exit":
                                break
                        inp = int(inp)
                        print(rdr.getchunks(inp))
	print(rdr)
  
