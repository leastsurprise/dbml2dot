# dbml2dot
Author: Antoine VIALLON

# Usage
```
pip install git+https://github.com/aviallon/dbml2dot.git
python -m dbml2dot -h
```

### Example
```
python -m dbml2dot -i schema.dbml -o schema.dot --type svg
```
This will output two files, one named `schema.dot` corresponding to the generated dot output,
and a svg file corresponding to the graph generated by graphviz.