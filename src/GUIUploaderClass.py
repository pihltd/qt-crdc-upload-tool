from PyQt6.QtWidgets import QApplication,  QMainWindow,  QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton, QFileDialog, QListWidget, QTextEdit, QProgressBar
from PyQt6.QtCore import QSize
#from PyQt6.QtGui import QPainter

from upload_config import Config

import logging

#from PyQt6 import QtCore, QtGui, QtWidgets

import os
from pathlib import Path
import yaml
from common.constants import UPLOAD_TYPE, UPLOAD_TYPES, FILE_NAME_DEFAULT, FILE_SIZE_DEFAULT, MD5_DEFAULT, \
    API_URL, TOKEN, SUBMISSION_ID, FILE_DIR, FILE_MD5_FIELD, PRE_MANIFEST, FILE_NAME_FIELD, FILE_SIZE_FIELD, RETRIES, OVERWRITE, \
    DRY_RUN, TYPE_FILE, FILE_ID_FIELD, OMIT_DCF_PREFIX, S3_START, FROM_S3, HEARTBEAT_INTERVAL_CONFIG, CLI_VERSION, ARCHIVE_MANIFEST
    
#class UploadProgressBar(QProgressBar):
#    def __init__(self):
#        super().__init__()
#        prog_bar = QProgressBar(self)
#        prog_bar.setGeometry(50, 100, 250, 30)
#        prog_bar.setValue(0)
    
class QTextEditLogger(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = QTextEdit(parent)
        self.widget.setReadOnly(True)
        
    def emit(self, record):
        msg = self.format(record)
        self.widget.insertPlainText(f"\n{msg}")


class GuiUploader(object):
    def windowSetup(self, MainWindow):
    #def __init__(self):
    #    super().__init__()
        
        #self.setWindowTitle("Data Submission Data File Upload")
        #MainWindow.setOjbectName("Main Window")
        
        self.configFile = None
        self.cliBinary = None
        self.buttoncolor = "#004F91"
        #self.clipboard = QApplication.clipboard()
    
        #
        #  Layouts
        #
        mainLayout = QVBoxLayout()
        step1Layout = QVBoxLayout()
        step2Layout = QVBoxLayout()
        step4Layout = QVBoxLayout()
        infolayout = QVBoxLayout()
        launchCloseLayout = QHBoxLayout()
        progresslayout = QVBoxLayout()
        
        #self.sectionbreak = QPainter.drawLine()
        #self.sectionbreak = QLabel("--------------------------------")
        
        
        self.step1label = QLabel("Step 1: Download a configuration file")
        self.step1explained = QLabel("Go to the Submission Portal and click on the 'Download Configuration File' button.  Supply the requested information and a configuration file will be downloaded to your computer")
        self.step1explained.setWordWrap(True)
        
        self.step2label = QLabel("Step 2: Select the configuration file")
        self.step2explained = QLabel("Clicke on the 'Select configuration file' button and select the configuration file downloaded in Step 1")
        self.step2explained.setWordWrap(True)
        self.fileDialogButton = QPushButton("Select configuration file")
        self.fileDialogButton.setStyleSheet("background-color:#47AEFF")
        self.fileDialogButton.clicked.connect(self.launchFileDialog)
        step1Layout.addWidget(self.step1label)
        step1Layout.addWidget(self.step1explained)
        step1Layout.addWidget(QLabel("--------------------------------"))
        
        step2Layout.addWidget(self.step2label)
        step2Layout.addWidget(self.step2explained)
        step2Layout.addWidget(self.fileDialogButton)
        step2Layout.addWidget(QLabel("--------------------------------"))
        
        step1widget = QWidget()
        step1widget.setLayout(step1Layout)
        step2widget = QWidget()
        step2widget.setLayout(step2Layout)
        
        configLayout = QVBoxLayout()
        self.step3label = QLabel("Step 3: Review")
        self.step3explained = QLabel("Review the information below.  If correct, proceed to step 4, if not, go back to Step 2 and upload a corrected configuration file.")
        self.step3explained.setWordWrap(True)
        self.configFileLabel = QLabel("Configuration file:")
        self.dataDirLabel = QLabel("Data directory:")
        self.submissionUUIDLabel = QLabel("Submission ID:")
        self.typeLabel = QLabel("Submission Type:")
        self.retriesLabel = QLabel("Number of retries:")
        self.overwriteLabel = QLabel("File overwrite status:")
        self.dryrunLabel = QLabel("Dry run status:")
        
        configLayout.addWidget(self.step3label)
        configLayout.addWidget(self.step3explained)
        configLayout.addWidget(self.configFileLabel)
        configLayout.addWidget(self.dataDirLabel)
        configLayout.addWidget(self.submissionUUIDLabel)
        configLayout.addWidget(self.typeLabel)
        configLayout.addWidget(self.retriesLabel)
        configLayout.addWidget(self.overwriteLabel)
        configLayout.addWidget(self.dryrunLabel)
        configLayout.addWidget(QLabel("--------------------------------"))
        
        configInfo = QWidget()
        configInfo.setLayout(configLayout)
        
        self.step4Label = QLabel("Step 4: Start the file upload")
        self.step4explained = QLabel("If the configuration information is correct, start the upload by clicking the 'Start File Upload' button.  NOTE: This program must remain running until all files have been uploaded to CRDC.")
        self.step4explained.setWordWrap(True)
        self.cliDialogButton = QPushButton("Start File Upload")
        self.cliDialogButton.setStyleSheet("background-color:#47AEFF")
        self.cliDialogButton.clicked.connect(self.fileUploadKickoff)
        
    
        step4Layout.addWidget(self.step4Label)
        step4Layout.addWidget(self.step4explained)
        step4Layout.addWidget(self.cliDialogButton)
        step4Layout.addWidget(QLabel("--------------------------------"))
        step4Widget = QWidget()
        step4Widget.setLayout(step4Layout)
        #self.cliInfo = QLabel("Upload Tool:")
        
        # Add exit button
        self.exitButton = QPushButton("Exit")
        self.exitButton.setStyleSheet("background-color:#47AEFF")
        self.exitButton.clicked.connect(self.close)
        launchCloseLayout.addWidget(self.exitButton)
        buttonwidget =QWidget()
        buttonwidget.setLayout((launchCloseLayout))
        
        # Add upload information section
        self.infolabel = QLabel("Uploading progress and informaiton")
        #self.info = QTextEdit()
        #self.info.setReadOnly(True)
        #self.info.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.info = QTextEditLogger(self)
        infolayout.addWidget(self.infolabel)
        infolayout.addWidget(self.info.widget)
        infolayout.addWidget(QLabel("--------------------------------"))
        infowidget = QWidget()
        infowidget.setLayout(infolayout)
        
        #Progress bar
        progLabel = QLabel("File Upload Progress")
        self.prog_bar = QProgressBar()
        self.prog_bar.setGeometry(50, 100, 250, 30)
        self.prog_bar.setValue(0)
        progresslayout.addWidget(progLabel)
        progresslayout.addWidget(self.prog_bar)
        progresswidget = QWidget()
        progresswidget.setLayout(progresslayout)
        
        
        mainWidget = QWidget()
        mainLayout.addWidget(step1widget)
        mainLayout.addWidget(step2widget)
        mainLayout.addWidget(configInfo)
        mainLayout.addWidget(step4Widget)
        mainLayout.addWidget(infowidget)
        mainLayout.addWidget(progresswidget)
        #mainLayout.addWidget(self.cliInfo)
        mainLayout.addWidget(buttonwidget)
        #mainLayout.addWidget(self.commandLine)
        
        mainWidget.setLayout(mainLayout)
        
        MainWindow.setCentralWidget(mainWidget)
        



