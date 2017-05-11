PYTHON3 = python3

TESTS := $(sort $(wildcard vterm/tests/*.test))
RUN_TESTS := $(patsubst %.test,%.test.via-harness,${TESTS})

test: ${RUN_TESTS}

%.test.via-harness: %.test
	PYTHON3=${PYTHON3} vterm/tests/run-test.pl $<
%.run: %
	./$< ${RUN_ARGS}


CC = gcc -pthread -fsanitize=address
CFLAGS = -std=c89 -g -O2
CFLAGS += -pedantic -Wall -Wextra
test: spawn-test.run
EXTRA_OBJECTS := $(addprefix vterm/c-sources/,spawn.o correct-strerror_r.o)
spawn-test: spawn-test.o ${EXTRA_OBJECTS}
spawn-test.run: RUN_ARGS=echo hello

${EXTRA_OBJECTS}: $(wildcard vterm/_c.*.so)

clean:
	rm -f *.o vterm/c-sources/*.o
