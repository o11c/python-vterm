PYTHON3 = python3

TESTS := $(sort $(wildcard vterm/tests/*.test))
RUN_TESTS := $(patsubst %.test,%.test.via-harness,${TESTS})

test: ${RUN_TESTS}

%.test.via-harness: %.test
	PYTHON3=${PYTHON3} vterm/tests/run-test.pl $<
