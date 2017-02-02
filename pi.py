from core import *

ser = createSerial('/dev/ttyAMA0')

ser.isOpen()

print "Waiting..."

while 1:
    try:
        out = ser.readline()
        if out != '':
            print(">>> %s"%out)
            if out[:3] == 'do:':
                command = out[4:]
                text = "Done"
                try:
                    exec(command)
                except Exception as e:
                    out = e
                    print("Error: %s is not valid"%command)
                    text = "Error: %s"%out
                sendmessage(ser, text)
            else:
                sendmessage(ser, "Ok")
        time.sleep(0.01)
    except KeyboardInterrupt:
        ser.close()
        break