.PHONY: install test run clean

install:
	pip3.7 install -r requirements.txt
	sudo ln -s $(PWD)/csctl/scripts/csctl-sh /usr/bin/csctl && chmod +x $(PWD)/csctl/scripts/csctl-sh
	sudo cp $(PWD)/csctl/csctl/scripts/csctl /etc/bash_completion.d/

test:
	python -m unittest discover -s tests 

run:
	python main.py

clean:
	rm -rf __pycache__  # Remove arquivos gerados pelo Python
	rm -rf *.pyc       # Remove arquivos de bytecode Python
	rm -rf *.pyo       # Remove arquivos otimizados Python
	rm -rf *.pyd       # Remove arquivos de extensão Python
	rm -rf .coverage   # Remove relatório de cobertura
