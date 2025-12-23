from os import path
import platform
import sys
import traceback
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import (
    QTranslator,
    QLocale,
)

from mainwindow import MainWindow
from resource_path import resource_path
from sc_logging import logger, log_file_path
from http_server import stop_http_server

def show_startup_error(error: Exception) -> None:
    message = (
        "ScoreSight hit an error during startup and needs to close.\n\n"
        f"{error}\n\n"
        f"Logs: {log_file_path}"
    )
    try:
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "ScoreSight failed to start", message)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        # only attempt splash when not on Mac OSX
        os_name = platform.system()
        if os_name != "Darwin":
            try:
                import pyi_splash  # type: ignore

                pyi_splash.close()
            except ImportError:
                pass
        app = QApplication(sys.argv)

        # Get system locale
        locale = QLocale.system().name()

        # Load the translation file based on the locale
        translator = QTranslator()
        locale_file = resource_path("translations", f"scoresight_{locale}.qm")
        # check if the file exists
        if not path.exists(locale_file):
            # load the default translation file
            locale_file = resource_path("translations", "scoresight_en_US.qm")
        if translator.load(locale_file):
            app.installTranslator(translator)

        # show the main window
        mainWindow = MainWindow(translator, app)
        mainWindow.show()

        app.exec()
        logger.info("Exiting...")

        stop_http_server()
    except Exception as error:
        logger.exception("Unhandled error during startup")
        show_startup_error(error)
        sys.exit(1)
