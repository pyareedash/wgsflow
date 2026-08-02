.PHONY: install doctor demo dry-run run test lint clean

install:
	pixi install
	pixi run install

doctor:
	pixi run wgsflow doctor --config config/demo.yaml

demo:
	pixi run wgsflow data synthetic --force

dry-run:
	pixi run wgsflow dry-run --config config/demo.yaml --cores 4

run:
	pixi run wgsflow run --config config/demo.yaml --cores 4

test:
	pixi run test

lint:
	pixi run lint

clean:
	pixi run wgsflow clean --yes
