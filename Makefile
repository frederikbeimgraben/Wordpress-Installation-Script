# Compile the python script into an executable using Cython

TARGET_FILE=wordpress-install.py
TARGET_C_FILE=build/$(patsubst %.py,%.c,$(TARGET_FILE))
TARGET_O_FILE=build/$(patsubst %.py,%,$(TARGET_FILE))

PYTHONLIBVER=python$(shell python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')$(shell python3-config --abiflags)

all: create_build_dir test_cython_installed compile_cython compile_c

create_build_dir:
	@echo "Creating build directory..."
	@mkdir -p build
	@echo "Build directory created."

test_cython_installed:
	@echo "Checking if Cython is installed..."
	@python3 -c "import Cython" || (echo "Cython is not installed. Please install it using 'pip install Cython'." && exit 1)
	@echo "Cython is installed."

compile_cython:
	@echo "Compiling the python script into an executable using Cython..."
	@cython -3 --embed $(TARGET_FILE) -o $(TARGET_C_FILE)
	@echo "Compilation successful."

compile_c:
	@echo "Compiling the generated C file: $(TARGET_C_FILE) into an executable..."
	@gcc -o $(TARGET_O_FILE) $(TARGET_C_FILE) -I/usr/include/$(PYTHONLIBVER) -l$(PYTHONLIBVER) -lpthread -lm -lutil -ldl
	@echo "Compilation successful."

clean:
	@echo "Cleaning up..."
	@rm -f $(TARGET_FILE:.py=.c)
	@echo "Cleanup successful."
