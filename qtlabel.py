#!/usr/bin/python
# -*- coding: utf-8 -*-

###############################################################################
# Tool for image concepts labeling.
#  ** Implemented in the Python language with QT.
###############################################################################

import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import ConfigParser

from PyQt4.QtGui import QMainWindow, QLabel, QPixmap, QImage, \
    QGridLayout, QHBoxLayout, QVBoxLayout, QPushButton, QRadioButton, \
    QMessageBox, QWidget
from PyQt4.QtCore import QSize, pyqtSlot
from PyQt4.Qt import Qt, QApplication

import sqlite3
import numpy as np

import label_common as lc


class ImView(QLabel):
    def __init__(self, parent, pixmap):
        super(ImView, self).__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setWindowFlags(
            Qt.Window | Qt.WindowStaysOnTopHint)
        self.pixmap = pixmap

    def resizeEvent(self, event):
        self.setPixmap(self.pixmap.scaled(
            self.size(), Qt.KeepAspectRatio))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.hide()


class ImShow(QLabel):
    imview = None

    def __init__(self, tb_name):
        super(ImShow, self).__init__()
        self.tb_name = tb_name
        self.setAlignment(Qt.AlignCenter)
        self.imname = None
        self.pixmap = None
        self.label = None
        self.cursor = None
        self.setMinimumSize(32, 32)
        self.status = '0'
        self.margin = QSize(10, 10)

    # Set Image
    def setImage(self, imname, cursor, label):
        self.imname = imname
        if None == self.imname:
            self.pixmap = None
            self.status = '0'
            self.setEnabled(False)
        else:
            if None != label:
                self.label = label
                self.cursor = cursor
                # SQL for view labeled image
                view_sql = "select %s from %s where img=?" % (
                    label, self.tb_name)
                cursor.execute(view_sql, (self.imname, ))
                item = cursor.fetchone()
                self.status = item[0]

            self.setEnabled(True)
            self.pixmap = QPixmap.fromImage(QImage(self.imname))
            self.setPixmap(self.pixmap.scaled(self.size() - self.margin,
                                              Qt.KeepAspectRatio))

    def paintEvent(self, event):
        super(ImShow, self).paintEvent(event)
        if None != self.pixmap:
            self.setPixmap(self.pixmap.scaled(self.size() - self.margin,
                                              Qt.KeepAspectRatio))
        if self.status == 'f':
            self.setStyleSheet("QLabel { background-color : red; }")
        elif self.status == 't':
            self.setStyleSheet("QLabel { background-color : blue; }")
        else:
            self.setStyleSheet("QLabel { background-color : green; }")

    # mouse click
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if ImShow.imview is None:
                ImShow.imview = ImView(self.parent(), self.pixmap)
                # ImShow.imview.resize(640, 640)
            ImShow.imview.pixmap = self.pixmap
            ImShow.imview.setPixmap(self.pixmap.scaled(
                ImShow.imview.size(), Qt.KeepAspectRatio
            ))
            ImShow.imview.showMaximized()
        elif self.label is None:
            QMessageBox.warning(
                self.parent(), "Attention!",
                unicode("Please choose a label!"))
        else:
            if self.status == 'f' or self.status == '0':
                self.updateLabel('t')
            elif self.status == 't':
                self.updateLabel('f')

    # update label information
    def updateLabel(self, status):
        self.status = status
        update_sql = "update %s set %s=? where img=?" % (self.tb_name,
                                                         self.label)
        self.cursor.execute(update_sql, (status, self.imname))


class MainWindow(QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()
        self.load_qt_cfg()
        self.initLabel()
        self.initUI()
        # show the first page
        self.setProc(0)
        self.KEY_PRESS_DELAY = 3600 * 24
        self.pressed_key = None

    def __del__(self):
        self.conn.commit()
        print "Bye!"

    def keyPressEvent(self, event):
        if event.isAutoRepeat() or self.pressed_key is not None:
            return
        if event.key() in [ord('W'), ord('w')]:
            self.btn_save.animateClick(self.KEY_PRESS_DELAY)
        elif event.key() in [ord('E'), ord('e')]:
            self.btn_prev.animateClick(self.KEY_PRESS_DELAY)
        elif event.key() in [ord('R'), ord('r')]:
            self.btn_next.animateClick(self.KEY_PRESS_DELAY)
        else:
            return
        self.pressed_key = event.key()

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat() or self.pressed_key != event.key():
            return
        if event.key() in [ord('W'), ord('w')]:
            self.btn_save.animateClick(0)
        elif event.key() in [ord('E'), ord('e')]:
            self.btn_prev.animateClick(0)
        elif event.key() in [ord('R'), ord('r')]:
            self.btn_next.animateClick(0)
        self.pressed_key = None

    # Load QT configuration
    def load_qt_cfg(self):
        # selected label
        self.sel_label = None

        config = ConfigParser.RawConfigParser()
        # Open
        try:
            config.read(lc.cfg_path)
        except:
            lc.perr("Invalid Configuration File!\n")
            sys.exit(1)

        # Image rows and cols
        try:
            self.cols = config.getint('qt', 'image_cols')
            self.rows = config.getint('qt', 'image_rows')
        except:
            self.rows = 4
            self.cols = 4
        self.pagesize = self.rows * self.cols

        # max number of labels per line
        try:
            self.nlabels = config.getint('qt', 'nlabels_per_line')
        except:
            self.nlabels = 12

    def initLabel(self):
        # Load common configuration
        (self.db_path, self.tb_name, self.imlist, self.labels) = \
            lc.load_cfg(lc.cfg_path)

        self.nimgs = len(self.imlist)
        self.npages = int(np.ceil(float(self.nimgs) / self.pagesize))

        # Check if the database exists
        lc.check_db(self.db_path, self.tb_name, self.imlist, self.labels)

        # Connect to the database
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def updateTask(self, label):
        # SQL for fetch labeled images
        self.prev_sql = "select img from %s where %s!='0'" % (
            self.tb_name, label)

        # SQL for view labeled image
        # view_sql = "select img, %s from %s where img=?" % (
        #     label, self.tb_name)
        # SQLs for update label information
        update_sql = {}
        # a_ = 1048673
        # s_ = 1048691
        d_ = 1048676
        f_ = 1048678
        update_sql[d_] = "update %s set %s='t' where img=?" % (
            self.tb_name, label)
        update_sql[f_] = "update %s set %s='f' where img=?" % (
            self.tb_name, label)

    # set current proc.
    def setProc(self, imidx):
        pos = imidx / self.pagesize * self.pagesize
        self.setImages(self.imlist[pos:(pos+self.pagesize)])
        self.pos = pos
        self.lcl_proc.setText("Proc: %d/%d" % (
            pos/self.pagesize+1, self.npages))
        if pos - self.pagesize < 0:
            self.btn_prev.setEnabled(False)
        else:
            self.btn_prev.setEnabled(True)
        if pos + self.pagesize >= self.nimgs:
            self.btn_next.setEnabled(False)
            # self.btn_save.setEnabled(False)
        else:
            self.btn_next.setEnabled(True)
            self.btn_save.setEnabled(True)
        print "Current position: ", self.pos

    def initUI(self):
        # QToolTip.setFont(QFont('SansSerif', 10))
        # self.setToolTip('This is a <b>QMainWindow</b> widget')

        # create buttons for selection of labels
        self.label_rbtns = [QRadioButton(unicode(label))
                            for label in self.labels.split()]

        # create widgets for showing images
        self.imshow = [ImShow(self.tb_name) for x in range(self.pagesize)]

        self.lcl_proc = QLabel("Proc: %d/%d" % (1, self.npages))
        self.btn_save = QPushButton("Save && Next(W)")
        self.btn_prev = QPushButton("Prev(E)")
        self.btn_next = QPushButton("Next(R)")

        # Layouts
        layout_labels = QGridLayout()
        layout_images = QGridLayout()
        layout_control = QHBoxLayout()
        layout_overall = QVBoxLayout()

        # setup labels selection buttons
        for i in range(len(self.label_rbtns)):
            chklcl = self.label_rbtns[i]
            layout_labels.addWidget(chklcl,
                                    i / self.nlabels, i % self.nlabels)

        # setup widgets for showing images
        for i in range(self.pagesize):
            layout_images.addWidget(self.imshow[i],
                                    i / self.cols, i % self.cols)

        # setup control buttons
        layout_control.addWidget(self.lcl_proc)
        layout_control.addWidget(self.btn_save)
        layout_control.addWidget(self.btn_prev)
        layout_control.addWidget(self.btn_next)

        # setup layout
        layout_overall.addLayout(layout_labels)
        layout_overall.addLayout(layout_images)
        layout_overall.addLayout(layout_control)

        # setup mainwindow
        centralWidget = QWidget()
        centralWidget.setLayout(layout_overall)
        self.setCentralWidget(centralWidget)
        self.setWindowTitle("Label")

        # signals and slots
        self.btn_save.clicked.connect(self.on_save)
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)
        for btn in self.label_rbtns:
            btn.clicked.connect(self.on_check)

    def setImages(self, images):
        for i in range(len(images)):
            self.imshow[i].setImage(images[i], self.cursor, self.sel_label)

        for i in range(len(images), len(self.imshow)):
            self.imshow[i].setImage(None, self.cursor, self.sel_label)

    @pyqtSlot()
    def on_check(self):
        if len(self.label_rbtns) is 1 and not self.label_rbtns[0].isChecked():
            self.label_rbtns[0].setChecked(True)
        cur_sel = None
        for i in range(len(self.labels.split())):
            print self.label_rbtns[i].isChecked()
            if self.label_rbtns[i].isChecked():
                cur_sel = self.labels.split()[i]
                break
        if self.sel_label == cur_sel:
            return
        self.sel_label = cur_sel
        self.updateTask(self.sel_label)

        # SQL for fetch unlabeled image
        fetch_sql = "select img from %s where %s='0'" % (
            self.tb_name, self.sel_label)
        self.cursor.execute(fetch_sql)
        item = self.cursor.fetchone()
        if None == item:
            QMessageBox.warning(
                self, "Attention!",
                unicode("Label '%s' is finished!" % self.sel_label))
            self.setProc(0)
        else:
            self.setProc(self.imlist.index(item[0]))

    @pyqtSlot()
    def on_save(self):
        if self.sel_label is None:
            QMessageBox.warning(
                self.parent(), "Attention!",
                unicode("Please choose a label!"))
            return
        for imshow in self.imshow:
            if imshow.status == '0':
                imshow.updateLabel('f')
        self.on_next()

    @pyqtSlot()
    def on_prev(self):
        self.conn.commit()
        pos = self.pos - self.pagesize
        self.setProc(pos)

    @pyqtSlot()
    def on_next(self):
        self.conn.commit()
        pos = self.pos + self.pagesize

        if pos >= self.nimgs:
            self.btn_save.setEnabled(False)
            return

        self.setProc(pos)


def main():
    app = QApplication(sys.argv)
    mainwindow = MainWindow()
    mainwindow.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    # Enable the hot keys on Mac OS
    # try:
    #     from PyQt4.Qt import qt_set_sequence_auto_mnemonic
    #     qt_set_sequence_auto_mnemonic(True)
    # except:
    #     pass

    main()
