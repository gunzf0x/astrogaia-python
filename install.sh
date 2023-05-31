#!/bin/bash

# Script to automatically install 'astrogaia-python.py' and its dependences
# Also, disables some features like automatically checking updates for some libraries


# Banner
print_banner() {
  echo -e "\033[1m╱╱╱╱╱╱╭╮\033[0m"
  echo -e "\033[1m╱╱╱╱╱╭╯╰╮\033[0m"
  echo -e "\033[1m╭━━┳━┻╮╭╋━┳━━┳━━┳━━┳┳━━╮\033[0m"
  echo -e "\033[1m┃╭╮┃━━┫┃┃╭┫╭╮┃╭╮┃╭╮┣┫╭╮┃\033[0m"
  echo -e "\033[1m┃╭╮┣━━┃╰┫┃┃╰╯┃╰╯┃╭╮┃┃╭╮┃\033[0m"
  echo -e "\033[1m╰╯╰┻━━┻━┻╯╰━━┻━╮┣╯╰┻┻╯╰╯\033[0m"
  echo -e "\033[1m╱╱╱╱╱╱╱╱╱╱╱╱╱╭━╯┃\033[0m"
  echo -e "\033[1m╱╱╱╱╱╱╱╱╱╱╱╱╱╰━━╯\033[0m"
  echo -e "\033[1m╭━━╮╱╱╱╱╱╭╮╱╱╱╭╮╭╮\033[0m"
  echo -e "\033[1m╰┫┣╯╱╱╱╱╭╯╰╮╱╱┃┃┃┃\033[0m"
  echo -e "\033[1m╱┃┃╭━╮╭━┻╮╭╋━━┫┃┃┃╭━━┳━╮\033[0m"
  echo -e "\033[1m╱┃┃┃╭╮┫━━┫┃┃╭╮┃┃┃┃┃┃━┫╭╯\033[0m"
  echo -e "\033[1m╭┫┣┫┃┃┣━━┃╰┫╭╮┃╰┫╰┫┃━┫┃\033[0m"
  echo -e "\033[1m╰━━┻╯╰┻━━┻━┻╯╰┻━┻━┻━━┻╯\033[0m"
  echo "by Francisco Carrasco Varela"
  echo -e "                       (PUC)\n"
}


# Check if a binary is present in the system
check_binary_presence() {
  local command="$1"
  local verbose="$2"
  
  if command -v "$command" >/dev/null 2>&1; then
    if [[ "$verbose" = true ]]; then
      echo "[+] '$command' command detected on the machine"
    fi
    return 0
  else
    if [[ "$verbose" = true ]]; then
      echo "[-] '$command' not detected on the machine. Please install it or check if it is located in your \$PATH"
    fi
    return 1
  fi
}


attempt_to_install_virtualvenv() {
  local env_name="$1"
  echo "[+] Attempting to install 'virtualenv' with the command 'pip3 install virtualenv'"
  pip3 install virtualenv && echo "[+] 'virtualvenv' installed succesfully!" \
  || echo "[-] Could not install 'virtualvenv'. Try to install it and rerun the script."
  # Attempt to create a virtualenv once it is installed
  virtualenv -p python3 "$env_name"
}

check_python_version() {
  local required_major=3
  local required_minor=10
  local version=$(python3 -V 2>&1 | awk '{print $2}')
  
  local major=$(echo "$version" | awk -F. '{print $1}')
  local minor=$(echo "$version" | awk -F. '{print $2}')
  
  if [ "$major" -eq "$required_major" ] && [ "$minor" -ge "$required_minor" ]; then
    echo "[+] Current Python3 version valid ('$version')"
  else
    echo "[-] Current Python3 version ('$version' running 'python3 -V' command) is lower than required ($required_major.$required_minor)"
    echo "    Please update your Python3 and pip3 version and retry"
    echo "    You can also skip this step providing '--ignore-check-python' if instead of running 'python3' command you use 'python3.10' to run Python scripts"
  fi
}


instructions() {
  local env_name="$1"
  echo -e "\nFollow these steps to activate the environment for 'astrogaia-python':"
  echo "# Activate the virtual environment"
  echo -e "i) Run 'source ${env_name}/bin/activate'"
  echo "# Run the Python3 script"
  echo -e "ii) Run 'astrogaia-python.py' script"
  echo "# Disable the virtual environment"
  echo -e "iii) Run 'deactivate'"
}

main() {
  local ignore_check_python3=false
  local name=astrogaia-env
  
  # Get user arguments/flags
  while [ $# -gt 0 ]; do
    case "$1" in
      --ignore-check-python)
        ignore_check_python3=true
        shift ;;

      *)
        shift ;;
    esac
  done
  
  # Print a pretty banner
  print_banner
  
  # Check current Python3 Version
  if [ "$ignore_check_python3" = false ]; then
    check_python_version
  else
    echo "[!] Not checking Python version (step skipped)..."
  fi

  # Check if 'git' command is installed
  check_binary_presence "git" true

  # Clone 'astrogaia-python' into the current repository
  echo "[+] Cloning 'astrogaia-python' repository..."
  git clone https://github.com/GunZF0x/astrogaia-python.git && cd astrogaia-python || exit 1

  # Check if virtualenv commands works
  virtualvenv -p python3 "$name" || python3 -m venv ${name} || attempt_to_install_virtualvenv "$name"

  # Once the virtualenv has been created, activate it
  source ${name}/bin/activate
 
  # Since we are located into 'astrogaia-python' directory, install the required Python libraries
  echo "[+] Updating and installing pip3 libraries"
  pip3 install --upgrade pip
  pip3 install -r requirements.txt

  # Once everything has been installed, run the script 
  python3 astrogaia-python.py -h && echo -e "\n\n[+] The script apparently works!" || echo "[-] Something went wrong when running the script"

  # Deactivate the Virtual Environment
  echo "[+] Disabling '$name' virtual environment..."
  deactivate && echo "[+] Virtual Environment disabled"

  # Disable update for 'pwntools' python library
  echo never > ~/.cache/.pwntools-cache-*/update || echo "[-] Could not find 'pwntools' cache into '~/.cache' directory to disable automatic updates for this library"
    
  # Print instructions for future usage
  instructions "$name"


  # Done
  echo -e "\n\n[+] Done! You should be good to go"
}



main "$@"
