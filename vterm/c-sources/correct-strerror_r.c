#define _POSIX_C_SOURCE 200112L
#include <string.h>


/*
 * The problem is that it's impossible to get the POSIX version of
 * strerror_r with _GNU_SOURCE defined, which is needed for pipe2() etc.
 *
 * While with glibc we could declare the underlying __xpg_strerror_r
 * function ourselves, that wouldn't work with other implementations.
 */
int correct_strerror_r(int errnum, char *buf, size_t buflen)
{
    return strerror_r(errnum, buf, buflen);
}
