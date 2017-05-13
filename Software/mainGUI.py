#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
import __GUI_images__
from __mainwindow__ import Ui_MainWindow
from PyQt5 import QtCore, QtGui, QtWidgets

from propertiesWindow import *
from reimaginedQuantum import *

def heavy_import():
    """ Imports matplotlib and NumPy.

    Useful to be combined with threading processes.
    """
    global plt, FigureCanvas, NavigationToolbar, EngFormatter, Axes
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import (
                            FigureCanvasQTAgg as FigureCanvas,
                            NavigationToolbar2QT as NavigationToolbar)
    from plotting import Axes

if CURRENT_OS == 'win32':
    import ctypes
    myappid = 'quantum.quantum.JuanBarbosa.01' # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

class Main(QtWidgets.QMainWindow, Ui_MainWindow):
    """
        Defines the mainwindow.

    Constants
    """
    DEFAULT_SAMP = 500
    DEFAULT_TPLOT = 100
    DEFAULT_TCHECK = 1000
    DEFAULT_CURRENT = 200
    TABLE_YGROW = 100
    EXTENSION_DATA = '.dat'
    EXTENSION_PARAMS = '.txt'
    SUPPORTED_EXTENSIONS = {EXTENSION_DATA : 'Plain text data file (*.dat)', '.csv' : 'CSV data files (*.csv)'}

    global DELIMITER
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)

        self.setupUi(self)
        self.output_name = self.save_line.text()
        self.extension = self.EXTENSION_DATA
        self.params_file = "%s_params%s"%(self.output_name[:-4], self.EXTENSION_PARAMS)

        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.DEFAULT_SAMP)
        self.plot_timer = QtCore.QTimer()
        if self.DEFAULT_SAMP > self.DEFAULT_TPLOT:
            timer = self.DEFAULT_SAMP
        else:
            timer = self.DEFAULT_TPLOT


        self.plot_timer.setInterval(timer)

        self.check_timer = QtCore.QTimer()
        self.check_timer.setInterval(self.DEFAULT_TCHECK)
        self.samp_spinBox.setValue(self.DEFAULT_SAMP)

        self.current_timer = QtCore.QTimer()
        if self.DEFAULT_SAMP > self.DEFAULT_CURRENT:
            timer = self.DEFAULT_SAMP
        else:
            timer = self.DEFAULT_CURRENT
        self.current_timer.setInterval(timer)
        """
        signals and events
        """
        self.port_box.installEventFilter(self)
        self.timer.timeout.connect(self.method_streamer)
        self.plot_timer.timeout.connect(self.update_plot)
        self.check_timer.timeout.connect(self.periodic_check)
        self.current_timer.timeout.connect(self.update_current_labels)
        self.save_button.clicked.connect(self.choose_file)
        self.stream_button.clicked.connect(self.method_streamer)
        self.channels_button.clicked.connect(self.channelsCaller)
        self.samp_spinBox.valueChanged.connect(self.method_sampling)
        self.coin_spinBox.valueChanged.connect(self.method_coinWin)
        self.port_box.currentIndexChanged.connect(self.select_serial)
        self.save_line.returnPressed.connect(self.save_location)
        self.ylength = self.table.rowCount()
        self.xlength = self.table.columnCount()

        self.data = None
        self.params_header = None
        """
        set
        """
        self.window = None
        self.serial = None
        self.port = None
        self.experiment = None
        self.ports = {}
        self.current_cell = 0
        self.last_row_saved = 0
        self.number_columns = 0
        self.format = None

        self.first_port = True
        """
        fig
        """
        self.fig = None

    def create_fig(self):
        self.fig, (ax_counts, ax_coins) = plt.subplots(2, sharex=True, facecolor='None', edgecolor='None')
        self.canvas = FigureCanvas(self.fig)
        self.plot_layout.addWidget(self.canvas)
        self.toolbar = NavigationToolbar(self.canvas,
                self.plot_widget, coordinates=True)

        self.plot_layout.addWidget(self.toolbar)
        self.ax_counts = Axes(self.fig, self.canvas, ax_counts, self.TABLE_YGROW,
                              "Counts", self.experiment.detectors)
        self.ax_coins = Axes(self.fig, self.canvas, ax_coins, self.TABLE_YGROW,
                             "Coincidences", self.experiment.coin_channels)

        for i in range(self.experiment.number_detectors):
            self.current_labels[i].set_color(self.ax_counts.colors[self.experiment.detectors[i].name])
        for j in range(self.experiment.number_coins):
            self.current_labels[1+j+i].set_color(self.ax_coins.colors[self.experiment.coin_channels[j].name])

        self.canvas.mpl_connect('draw_event', self._draw_event)
        self.canvas.draw_idle()
        self.fig.set_tight_layout(True)

    def save_param(self, label, value, units):
        current_time = strftime("%H:%M:%S", localtime())
        if value == None:
            message = label
            if units == None:
                message = "%s %s%s\n"%(current_time, DELIMITER, label)
        else:
            message = "%s %s%s: %d %s\n"%(current_time, DELIMITER, label, value, units)
        with open(self.params_file, 'a') as file_:
            file_.write(message)

    def create_current_labels(self):
        self.current_labels = []
        for detector in self.experiment.detectors:
            name = detector.name
            label = AutoSizeLabel(name, "0")
            label.setObjectName("current_label_%s"%detector)
            self.verticalLayout_2.addWidget(label)
            self.current_labels.append(label)
        for coin in self.experiment.coin_channels:
            name = coin.name
            label = AutoSizeLabel(name, "0")
            label.setObjectName("current_label_%s"%detector)
            self.verticalLayout_2.addWidget(label)
            self.current_labels.append(label)

    def split_extension(self, text):
        try:
            name, ext = text.split('.')
            ext = ".%s"%ext
        except:
            name = text
            ext = ''

        if not ext in self.SUPPORTED_EXTENSIONS.keys() and ext != "":
            raise Exception("Current extension '%s' is not valid."%ext)

        return name, ext

    def reallocate_output(self, name, remove_old = False):
        params = "%s_params%s"%(name, self.EXTENSION_PARAMS)
        new = "%s%s"%(name, self.extension)
        if new != self.output_name and self.data != None:
            with open(new, "a") as file_:
                with open(self.output_name, "r") as old:
                    for line in old:
                        file_.write(line)
            self.data.output_file = new
            if remove_old:
                os.remove(self.output_name)
            if params != self.params_file:
                with open(params, "a") as file_:
                    with open(self.params_file, "r") as old:
                        print(params, self.params_file)
                        for line in old:
                            file_.write(line)
                if remove_old:
                    os.remove(self.params_file)

        self.output_name = new
        self.params_file = params

    def include_params(self, output, params, save = False, end = False):
        if self.data != None:
            if not self.data.empty:
                if save:
                    self.data.save()
                if end:
                    temp = "%sTEMP"%params
                    with open(temp, "w") as file:
                        file.write("##### PARAMETERS USED #####\n%s\n"%self.params_header)
                        with open(params, "r") as params_:
                            for line in params_:
                                file.write(line)
                    os.remove(params)
                    os.rename(temp, params)
            elif end:
                os.remove(self.params_file)
                os.remove(self.output_name)


    def save_location(self):
        new = self.save_line.text()
        try:
            name, ext = self.split_extension(new)
            if ext != '':
                self.extension = ext
            self.reallocate_output(name, remove_old = True)
        except Exception as e:
            self.save_line.setText(self.output_name)
            self.errorWindow(e)

    def eventFilter(self, source, event):
        """ Creates event to handle serial combobox opening.
        """
        if (event.type() == QtCore.QEvent.MouseButtonPress and source is self.port_box):
            self.serial_refresh()
        return QtWidgets.QWidget.eventFilter(self, source, event)

    def serial_refresh(self):
        """ Loads serial port described at user combobox.
        """
        current_ports = findPort()
        n = 0
        for x in current_ports.items():
            if x in self.ports.items():
                n += 1
        if n != len(current_ports) or n == 0:
            self.port_box.clear()
            self.ports = current_ports
            for port in self.ports:
                if CommunicationPort(self.ports[port]).test():
                    self.port_box.addItem(port)

        self.port_box.setCurrentIndex(-1)

    def select_serial(self, index, error_capable = True):
        """ Selects port at index position of combobox.
        """
        if index != -1 and not self.first_port:
            new_port = self.port_box.itemText(index)
            try:
                new_port = self.ports[new_port]
            except:
                new_port = ''
            if new_port != '':
                if self.serial != None:
                    try:
                        self.serial.close()
                    except CommunicationError:
                        pass
                    self.serial = None
                self.port = new_port
                try:
                    self.serial = CommunicationPort(self.port)
                    self.channels_button.setDisabled(False)
                    if self.window != None:
                        self.window.update()
                except Exception as e:
                    e = type(e)("Serial selection: %s"%str(e))
                    if error_capable:
                        self.errorWindow(e)
            else:
                self.widget_activate(True)

        self.first_port = False


    def widget_activate(self, status):
        """
        most of the tools will be disabled if there is no UART detected
        """
        self.samp_spinBox.setDisabled(status)
        self.coin_spinBox.setDisabled(status)
        self.channels_button.setDisabled(status)
        # if status:
        self.stream_activate(status)

    def start_experiment(self):
        if self.format == None:
            self.stream_activate(False)
            self.create_table()
            self.header = np.zeros(self.number_columns, dtype=object)
            self.widget_activate(False)
            self.format = [r"%d" for i in range(self.number_columns)]
            self.format[0] = "%.3f"
            self.format = DELIMITER.join(self.format)
            self.data = RingBuffer(self.TABLE_YGROW, self.number_columns, self.output_name, self.format)
            self.create_current_labels()
            self.create_fig()

        if self.serial != None and self.window != None:
            if not self.window.error_ocurred:
                self.widget_activate(False)

    def stream_activate(self, status):
        self.stream_button.setDisabled(status)

    def create_table(self):
        self.number_columns = self.experiment.number_detectors + self.experiment.number_coins + 1
        self.table.setRowCount(self.TABLE_YGROW)
        self.table.setColumnCount(self.number_columns)
        self.table.setItem(0, 0, QtWidgets.QTableWidgetItem("Time (s)"))
        for i in range(self.experiment.number_detectors):
            self.table.setItem(0, i+1, QtWidgets.QTableWidgetItem(self.experiment.detectors[i].name))
        for j in range(self.experiment.number_coins):
            self.table.setItem(0, i+j+2, QtWidgets.QTableWidgetItem(self.experiment.coin_channels[j].name))

        headers = [self.table.item(0,i).text() for i in range(self.number_columns)]
        with open(self.output_name, 'a') as file_:
            text = DELIMITER.join(headers)
            file_.write("%s\n"%text)

    def choose_file(self):
        """
        user interaction with saving file
        """
        dlg = QtWidgets.QFileDialog()
        dlg.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        dlg.setFileMode(QtWidgets.QFileDialog.AnyFile)
        nameFilters = [self.SUPPORTED_EXTENSIONS[extension] for extension in self.SUPPORTED_EXTENSIONS]
        dlg.setNameFilters(nameFilters)
        dlg.selectNameFilter(self.SUPPORTED_EXTENSIONS[self.extension])
        if dlg.exec_():
            name = dlg.selectedFiles()[0]
            try:
                extension = self.split_extension(name)[1]
                if extension == "":
                    name += self.extension
                self.save_line.setText(name)
                self.save_location()
            except Exception as e:
                self.errorWindow(e)

    def channelsCaller(self):
        """
        creates a property window to define number of channels
        """
        if self.window == None:
            ans1 = os.path.exists(self.output_name)
            ans2 = os.path.exists(self.params_file)
            if ans1 or ans2:
                QtWidgets.QMessageBox.warning(self, "File exists",
                    "The selected file already exists.\nData will be appended.")
            self.window = PropertiesWindow(self)
        self.window.show()

    def periodic_check(self):
        try:
            self.experiment.periodic_check()
        except Exception as e:
            self.errorWindow(e)
        samp = self.experiment.get_sampling_value()
        coin = self.experiment.get_coinwin_value()
        if self.samp_spinBox.value() != samp:
            self.samp_spinBox.setValue(samp)
        if self.coin_spinBox.value() != coin:
            self.coin_spinBox.setValue(coin)

        values = self.experiment.get_detectors_timers_values()
        self.window.set_values(values)

    def start_clocks(self):
        self.timer.start()
        self.plot_timer.start()
        self.check_timer.start()
        self.current_timer.start()

    def stop_clocks(self):
        self.timer.stop()
        self.plot_timer.stop()
        self.check_timer.stop()
        self.current_timer.stop()

    def update_current_labels(self):
        for i in range(self.experiment.number_detectors):
            value = self.table.item(self.current_cell, i+1).text()
            self.current_labels[i].change_value(value)
        for j in range(self.experiment.number_coins):
            value = self.table.item(self.current_cell, j+i+2).text()
            self.current_labels[j+i+1].change_value(value)

    def method_streamer(self):
        try:
            if self.timer.isActive() and self.sender() == self.stream_button:
                self.stop_clocks()
                self.data.save()
                self.save_param("Streaming stoped.", None, None)
                self.stream_button.setStyleSheet("background-color: none")

            elif not self.timer.isActive():
                self.stream_button.setStyleSheet("background-color: green")
                self.window.send_data()
                self.method_sampling(self.samp_spinBox.value(), error_capable = False)
                self.method_coinWin(self.coin_spinBox.value(), error_capable = False)
                self.save_param("Streaming started.", None, None)
                self.start_clocks()

            time_, detectors, coins = self.experiment.current_values()


            actual = self.table.rowCount()
            if (actual - self.current_cell) <= self.TABLE_YGROW:
                self.table.setRowCount(self.TABLE_YGROW + actual)

            if type(detectors) is list:
                if self.current_cell == 0:
                    self.init_time = time()
                    current_time = asctime(localtime())
                    self.params_header = "Reimagined Quantum experiment began at %s"%current_time
                time_ = time_ - self.init_time
                if time_ < 0:
                    time_ = 0
                values = [time_] + detectors + coins
                values = np.array(values)
                values = values.reshape((1, values.shape[0]))
                self.data.extend(values)
                for i in range(self.experiment.number_detectors):
                    value = "%d"%detectors[i]
                    cell = QtWidgets.QTableWidgetItem(value)
                    self.table.setItem(self.current_cell+1, i+1, cell)
                    cell.setFlags(QtCore.Qt.ItemIsEnabled)

                for j in range(self.experiment.number_coins):
                    value = "%d"%coins[j]
                    cell = QtWidgets.QTableWidgetItem(value)
                    self.table.setItem(self.current_cell+1, i+j+2, cell)
                    cell.setFlags(QtCore.Qt.ItemIsEnabled)

                cell = QtWidgets.QTableWidgetItem("%.3f"%time_)
                self.table.setItem(self.current_cell+1, 0, cell)
                self.table.scrollToItem(cell)
                self.current_cell += 1

        except Exception as e:
            self.errorWindow(e)

    def method_sampling(self, value, error_capable = True):
        self.timer.setInterval(value)
        if value > self.DEFAULT_TPLOT:
            self.plot_timer.setInterval(value)
        else:
            self.plot_timer.setInterval(self.DEFAULT_TPLOT)

        if value > self.DEFAULT_CURRENT:
            self.current_timer.setInterval(value)
        else:
            self.current_timer.setInterval(self.DEFAULT_CURRENT)
        try:
            self.experiment.set_sampling(value)
        except Exception as e:
            if error_capable:
                self.errorWindow(e)
            else:
                raise e

        self.save_param("Sampling Time", value, "ms")

    def method_coinWin(self, value, error_capable = True):
        try:
            self.experiment.set_coinWindow(value)
        except Exception as e:
            if error_capable:
                self.errorWindow(e)
            else:
                raise e
        self.save_param("Coincidence window", value, "ns")

    def _draw_event(self, *args):
        self.ax_coins.set_background()
        self.ax_counts.set_background()

    def update_plot(self):
        if self.current_cell > 1:
            data = self.data[:]
            times = np.arange(data.shape[0])
            ychanged1 = self.ax_counts.update_data(times, data)
            ychanged2 = self.ax_coins.update_data(times, data[:, self.experiment.number_detectors:])
            if ychanged1 or ychanged2:
                self.ax_coins.clean()
                self.ax_counts.clean()
                self.ax_coins.set_limits()
                self.ax_counts.set_limits()
                self.fig.canvas.draw()
                self.ax_coins.draw_artist()
                self.ax_counts.draw_artist()
                self.fig.canvas.flush_events()
            else:
                self.fig.canvas.restore_region(self.ax_coins.background)
                self.fig.canvas.restore_region(self.ax_counts.background)
                self.ax_coins.draw_artist()
                self.ax_counts.draw_artist()
                self.ax_counts.blit()
                self.ax_coins.blit()

    def errorWindow(self, error):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Warning)

        if type(error) == CommunicationError or type(error) == ExperimentError:
            self.stop_clocks()
            self.serial = None
            self.serial_refresh()
            self.widget_activate(True)
            self.stream_button.setStyleSheet("background-color: red")
            msg.setIcon(QtWidgets.QMessageBox.Critical)

        msg.setText("An Error has ocurred.")
        msg.setInformativeText(str(error))
        msg.setWindowTitle("Error")
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        msg.exec_()

    def closeEvent(self, event):
        quit_msg = "Are you sure you want to exit the program?"
        reply = QtWidgets.QMessageBox.question(self, 'Exit',
                         quit_msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if reply ==QtWidgets.QMessageBox.Yes:
            self.include_params(self.output_name, self.params_file, save = True, end = True)
            event.accept()
        else:
            event.ignore()

if __name__ == "__main__":
   app = QtWidgets.QApplication(sys.argv)
   splash_pix = QtGui.QPixmap(':/splash.png')
   splash = QtWidgets.QSplashScreen(splash_pix, QtCore.Qt.WindowStaysOnTopHint)
   progressBar = QtWidgets.QProgressBar(splash)
   progressBar.setGeometry(250, 320, 100, 20)
   #progressBar.setStyleSheet(DEFAULT_STYLE)
   splash.show()
   app.processEvents()
   app.setWindowIcon(QtGui.QIcon(':/icon.png'))

   if CURRENT_OS == 'win32':
       import ctypes
       myappid = 'quantum.quantum.JuanBarbosa.01' # arbitrary string
       ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

   progressBar.setValue(15)

   thread = Thread(target = heavy_import)
   thread.setDaemon(True)
   thread.start()
   i = 15
   while thread.is_alive():
       if i < 95:
           i += 1
           progressBar.setValue(i)
       sleep(0.1)

   plt.rcParams.update({'font.size': 8})

   main = Main()
   progressBar.setValue(100)
   main.show()
   splash.close()
   sys.exit(app.exec_())