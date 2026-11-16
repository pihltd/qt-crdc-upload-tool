# Graphical (pyqt6) front end for the CRDC cli uploader
# In theory, this should be a replacement for uploader.py

# Imports from uploader.py
import os
from pathlib import Path
import logging

from bento.common.utils import get_logger, LOG_PREFIX, get_time_stamp
from common.constants import UPLOAD_TYPE, S3_BUCKET, FILE_NAME_DEFAULT, BATCH_STATUS, DRY_RUN, \
    BATCH_BUCKET, BATCH, BATCH_ID, FILE_PREFIX, TEMP_CREDENTIAL, SUCCEEDED, ERRORS, BATCH_CREATED, BATCH_UPDATED, \
    FILE_PATH, SKIPPED, TYPE_FILE, CLI_VERSION, HEARTBEAT_INTERVAL_CONFIG, PRE_MANIFEST, FILE_ID_DEFAULT, SUBFOLDER_FILE_NAME, \
    OVERWRITE, FILE_DIR, SUBMISSION_ID, RETRIES
from common.graphql_client import APIInvoker
from common.utils import dump_dict_to_tsv, get_exception_msg
from upload_config import Config
from file_validator import FileValidator
from file_uploader import FileUploader
from process_manifest import process_manifest_file
from common.upload_heart_beater import UploadHeartBeater


#PyQT6 imports
from GUIUploaderClass import GuiUploader
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog
#from PyQt6.QtCore import QSize
#from PyQt6.QtGui import QTextCursor

#Set up logging
if LOG_PREFIX not in os.environ:
    os.environ[LOG_PREFIX] = 'Uploader Main'

log = get_logger('FileLoader')

class MainWindow(QMainWindow, GuiUploader):
    def __init__(self):
        super().__init__()
        self.resize(640,500)
        self.setWindowTitle("CRDC Data File Uploader")
        self.windowSetup(self)
        self.config = None
        self.s3_manifest_url = None
        app_name = 'TEMP_NAME'
        formatter = logging.Formatter(f'<14>1 %(asctime)s.%(msecs)03dZ - {app_name} %(process)d - - %(levelname)s: (%(name)s) %(message)s',
                                          "%Y-%m-%dT%H:%M:%S")
        self.info.setFormatter(formatter)
        logging.getLogger().addHandler(self.info)
        
        

    def launchFileDialog(self):
        configDialog = QFileDialog(self)
        configDialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        configDialog.setViewMode(QFileDialog.ViewMode.Detail)
        configDialog.setDirectory(os.path.expanduser("~"))
        if configDialog.exec():
            fileNames = configDialog.selectedFiles()
            self.configFile = str(Path(fileNames[0]))
            self.config = Config(self.configFile)
            # Safety check
            result, msg = self.config.check_version()
            if result == 0:
                log.warning(msg)
            elif result == -1:
                log.error(msg)
            else:
                log.info(msg)
            if not self.config.validate():
                    log.error("Failed to upload files: missing required valid parameter(s)!")
                    log.info("Failed to upload files: invalid parameter(s)!  Please check log file in tmp folder for details.")
            self.s3_manifest_url = self.config.data[PRE_MANIFEST] if self.config.data.get(PRE_MANIFEST) and self.config.data[PRE_MANIFEST].startswith("s3://") else None
            self.configFileLabel.setText(f"Configuration file: {self.configFile}")
            self.dataDirLabel.setText(f"Data directory: {self.config.data[FILE_DIR]}")
            self.submissionUUIDLabel.setText(f"Submission UUID: {self.config.data[SUBMISSION_ID]}")
            self.typeLabel.setText(f"Submission Type: {self.config.data[UPLOAD_TYPE]}")
            self.retriesLabel.setText(f"Number of retries: {self.config.data[RETRIES]}")
            self.overwriteLabel.setText(f"File overwrite status: {self.config.data[OVERWRITE]}")
            self.dryrunLabel.setText(f"Dry run status: {self.config.data[DRY_RUN]}")
    
    
    
    
    def fileUploadKickoff(self):
        apiInvoker = APIInvoker(self.config.data)
        result, data_file_config = apiInvoker.get_data_file_config(self.config.data["submission"])
        if not result or not data_file_config:
            log.error("Failed to upload files: can't get data file config!")
            log.info("Failed to upload files: can't get data file config! Please check log file in tmp folder for details.")
        if not self.config.validate_file_config(data_file_config):
            log.error("Failed to upload files: invalid file config!")
            log.info("Failed to upload files: invalid file config! Please check log file in tmp folder for details.")
        validator = FileValidator(self.config.data)
        if not validator.validate():
            log.error("Failed to upload files: found invalid file(s)!")
            log.info("Failed to upload files: found invalid file(s)!  Please check log file in tmp folder for details.")
           
        file_list = validator.fileList
        archive_files_info = validator.archive_files_info
        if self.config.data.get(DRY_RUN, False) and self.config.data[DRY_RUN] == True:
            log.info("File validations are completed in dry run mode.")
        if validator.invalid_count == 0:
            #step 3: create a batch
            file_array = [ item[SUBFOLDER_FILE_NAME] if item.get(SUBFOLDER_FILE_NAME) else item.get(FILE_NAME_DEFAULT) for item in file_list]
            newBatch = None
            if apiInvoker.create_batch(file_array):
                newBatch = apiInvoker.new_batch
                if not newBatch.get(BATCH_BUCKET) or not newBatch[FILE_PREFIX] or not newBatch.get(BATCH_ID):
                    log.error("Failed to upload files: can't create new batch!")
                    log.info("Failed to upload files: can't create new batch! Please check log file in tmp folder for details.")
                self.config.data[S3_BUCKET] = newBatch.get(BATCH_BUCKET)
                self.config.data[FILE_PREFIX] = newBatch[FILE_PREFIX]
                self.config.data[BATCH_ID] = newBatch.get(BATCH_ID)
                self.config.data[BATCH] = newBatch
                log.info(f"New batch is created: {self.config.data[BATCH_ID]} at {newBatch[BATCH_CREATED]}")
            else:
                log.error("Failed to upload files: can't create new batch!")
                log.info("Failed to upload files: can't create new batch! Please check log file in tmp folder for details.")
    
            #step 4: get aws sts temp credential for uploading files to s3 bucket.
            if not apiInvoker.get_temp_credential():
                log.error("Failed to upload files: can't get temp credential!")
                log.info("Failed to upload files: can't get temp credential! Please check log file in tmp folder for details.")
                file_array = [{"fileName": item[FILE_NAME_DEFAULT], "succeeded": False, "errors": ["Failed to upload files: can't get temp credential!"]} for item in file_list]
            else:
                temp_credential = apiInvoker.cred
                self.config.data[TEMP_CREDENTIAL] = temp_credential
                #step 5: upload all files to designated s3 bucket
                loader = FileUploader(self.config.data, file_list, validator.md5_cache, validator.md5_cache_file, archive_files_info)
                # create upload heart beater instance
                upload_heart_beater = UploadHeartBeater(self.config.data[BATCH_ID], apiInvoker, self.config.data[HEARTBEAT_INTERVAL_CONFIG])
                try:
                    # start heart beater right before uploading files
                    if upload_heart_beater:
                        upload_heart_beater.start()
                    result = loader.upload()
                    if not result:
                        log.error("Failed to upload files: can't upload files to bucket!")
                        log.info("Failed to upload files: can't upload files to bucket! Please check log file in tmp folder for details.")
                    else:
                        #write filelist to tsv file and save to result dir
                        log.info("File uploading completed!")
                        if self.config.data[UPLOAD_TYPE] == TYPE_FILE:
                            # process manifest file
                            if not validator.has_file_id:
                                # set file id to file_list
                                for i, file_info in enumerate(newBatch["files"]):
                                    file_list[i][FILE_ID_DEFAULT] = file_info.get(FILE_ID_DEFAULT)
                            process_manifest_file(log, self.config.data.copy(), validator.has_file_id, file_list, validator.manifest_rows, self.s3_manifest_url)  
                    # stop heartbeat after uploading completed
                    if upload_heart_beater:
                        upload_heart_beater.stop()
                        upload_heart_beater = None
                    
                except KeyboardInterrupt:
                    # stop heartbeat if interrupted
                    if upload_heart_beater:
                        upload_heart_beater.stop()
                        upload_heart_beater = None
                    error = 'File uploading is interrupted.'
                    log.info(error)
                    for item in file_list:
                        if not item.get(SUCCEEDED, False):
                            item[ERRORS] = item[ERRORS].append(error) if item.get(ERRORS) else [error]
                            item[SUCCEEDED] = False
                finally:
                    #set fileList for update batch
                    file_array = [{"fileName": item[SUBFOLDER_FILE_NAME] if item.get(SUBFOLDER_FILE_NAME) else item.get(FILE_NAME_DEFAULT), "succeeded": item.get(SUCCEEDED, False), "errors": item.get(ERRORS, []), "skipped": item.get(SKIPPED, False)} for item in file_list]
                    #step 6: update the batch
                    if apiInvoker.update_batch(newBatch[BATCH_ID], file_array):
                        batch = apiInvoker.batch
                        log.info(f"The batch is updated: {newBatch[BATCH_ID]} with new status: {batch[BATCH_STATUS]} at {batch[BATCH_UPDATED]} ")
                    else:
                        log.error(f"Failed to update batch, {newBatch[BATCH_ID]}!")
                        log.info(f"Failed to update batch, {newBatch[BATCH_ID]}! Please check log file in tmp folder for details.")
        else:
            log.error(f"Found total {validator.invalid_count} file(s) are invalid!")
        
        #step 6: #dump file_list with uploading status and errors to tmp/reports dir
        try:
            file_path = f"./tmp/upload-report-{get_time_stamp()}.tsv"
            #filter out file path in the file list
            file_list = [ {i:a[i] for i in a if i!=FILE_PATH} for a in file_list]
            dump_dict_to_tsv(file_list, file_path)
            log.info(f"Uploading report is created at {file_path}!")
        except Exception as e:
            log.exception(f"Failed to dump uploading report files: {get_exception_msg()}.")
            log.info(f"Failed to dump uploading report files: {get_exception_msg()}.")

if __name__ == '__main__':
   
    app = QApplication([])
    daGUI = MainWindow()
    daGUI.show()
    app.exec()
    