# qt-crdc-upload-tool
# Experimental Graphical CRDC data file upload tool
It cannot be stressed enough that **this is an experiment and under construction**.  It may work, then again, it may not.  That's the polite way to say that only an idiot would use this for production uses.

## Background
Data file uploads to the CRDC Submission Portal are done using a command line Python script, the [crdc-datahub-cli-uploader](https://github.com/CBIIT/crdc-datahub-cli-uploader/tree/master).  Occaisionally, there are submitters who are not comfortable using anything on the command line, and this interface is an experiment to see if a graphical interface makes any sense.  

## Warning
The biggest reason to NOT use this tool is the same reason that upload via a browser isn't offered:  For large data files, a graphical interface means that the computer displaying the interface *must* be left running for the entire duration of the upload.  For projects with data stored in remote storage like AWS S3, or storage at a university compute center, the original command line tool should be used.


## Development approach
This project can be considered a fork of the original command line tool and the goal is to preserve as much of the original code as possible.  The  GUI itself uses [PyQt6](https://pypi.org/project/PyQt6/) as the graphical library.

### Files

- **src/GUIuploader.py**: This replaces the origininal **uploader.py**.  While it preserves much of the original code, it has been significantly altered to support the GUI.
- **src/GUIUploaderClass.py**: This has no counterpart in the original and is used to hold the layout and graphical elements of the tool.
- **src/upload_config.py**:  This retains almost all of the code of the original (and has not been renamed), however the parts of the *__init__* function relating to *argparse* have been removed since they are not needed.
- **src/copier.py**:  Original file, no changes.
- **src/file_uploader.py**: Original file, no changes.
- **src/file_validator.py**: Original file, no changes.

