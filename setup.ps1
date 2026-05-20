python -m venv venv
# Windows
.\\venv\\Scripts\\activate
# Mac/Linux
# source venv/bin/activate

# install requirements and package
pip install -r ./requirements/dev.txt
pip install -e .