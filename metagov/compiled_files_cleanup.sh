# Delete all __pycache__ and *.pyc compiled files

find . | \
  grep -E "(__pycache__|\.pyc$)" | \
  xargs rm -rf

# for command line:
# find . | grep -E "(__pycache__|\.pyc$)" | xargs rm -rf

