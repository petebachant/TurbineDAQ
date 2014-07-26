echo Building GUI

call pyuic4 mainwindow.ui > mainwindow.py

echo Building resource file

call pyrcc4 -py3 icons/resources.qrc -o resources_rc.py

echo Done