#define _GNU_SOURCE
#include "spawn.h"

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/uio.h>
#include <sys/wait.h>
#include <unistd.h>

#include "correct-strerror_r.h"

/*
 * Before changing anything, be VERY careful that this won't introduce
 * any undefined behavior! This code was written very carefully!
 *
 * While only a C89 *compiler* is needed, additional *library* functions
 * are absolutely needed (pipe2, etc).
 */

/*
 * Works *without* multiple evaluation of macro arguments.
 */
#define zero_of_type(val) (false ? (val) : 0)
#define maybe_negative(val) (( zero_of_type(val) - 1) < 0)

/*
 * Multiple evaluation of denominator - but it should usually be constant.
 */
#define ceil_div(num, den) (((num) + ((den) - 1)) / (den))
#define bit_width(type) (sizeof(type) * CHAR_BIT)
/* Compute as if octal, plus sign bit and NUL terminator */
#define INT_STR_BUF_SIZE (1 + ceil_div(bit_width(uintmax_t), 3) + 1)

static char *int_str_unsigned(char buf[INT_STR_BUF_SIZE], uintmax_t val)
{
    char *p = buf + INT_STR_BUF_SIZE;
    --p;
    *p = '\0';
    do
    {
        --p;
        *p = '0' + val % 10;
        val /= 10;
    }
    while (val);
    return p;
}
static char *int_str_signed(char buf[INT_STR_BUF_SIZE], intmax_t val)
{
    bool negative = (val < 0);
    uintmax_t uval = negative ? -(uintmax_t)val : (uintmax_t)val;
    char *p = int_str_unsigned(buf, uval);
    if (negative)
    {
        --p;
        *p = '-';
    }
    return p;
}
#define int_str(buf, val) (maybe_negative(val) ? int_str_signed((buf), (val)) : int_str_unsigned((buf), (val)))

char *iov_to_str(struct iovec *iov, size_t iov_cnt)
{
    char *rv;
    size_t sz = 0, i;
    for (i = 0; i < iov_cnt; ++i)
    {
        sz += iov[i].iov_len;
    }
    rv = malloc(sz + 1);
    sz = 0;
    for (i = 0; i < iov_cnt; ++i)
    {
        memcpy(rv + sz, iov[i].iov_base, iov[i].iov_len);
        sz += iov[i].iov_len;
    }
    rv[sz] = '\0';
    return rv;
}
static void iov_append_str(struct iovec *iov, size_t *iov_cnt, const char *str)
{
    iov[*iov_cnt].iov_base = (char *)str;
    iov[*iov_cnt].iov_len = strlen(str);
    ++*iov_cnt;
}
static void iov_append_signal(struct iovec *iov, size_t *iov_cnt, int status, char msg_int_buf[INT_STR_BUF_SIZE])
{
    if (WIFSIGNALED(status))
    {
        iov_append_str(iov, iov_cnt, "killed by signal ");
        iov_append_str(iov, iov_cnt, int_str(msg_int_buf, WTERMSIG(status)));
        if (WCOREDUMP(status))
        {
            iov_append_str(iov, iov_cnt, " (core dumped)");
        }
    }
    else /* if (WIFEXITED(status)) */
    {
        iov_append_str(iov, iov_cnt, "exited with status ");
        iov_append_str(iov, iov_cnt, int_str(msg_int_buf, WEXITSTATUS(status)));
    }
}

static void writev_fully(int fd, struct iovec *iov, size_t iov_cnt)
{
    while (true)
    {
        ssize_t tmp = writev(fd, iov, iov_cnt);
        if (tmp == -1)
        {
            /* Nothing we can do at this stage. */
            abort();
        }
        while (tmp >= (ssize_t)iov->iov_len)
        {
            tmp -= iov->iov_len;
            iov++, iov_cnt--;
            if (!iov_cnt)
                return;
        }
        iov->iov_base = (char *)iov->iov_base + tmp;
        iov->iov_len -= tmp;
    }
}

static char *strerror_with_prefix(const char *pfx, int err)
{
    char buf[1024];
    int tmp;
    char *out;
    char *p;
    size_t pfx_len;
    size_t buf_len;
    size_t out_len;

    tmp = correct_strerror_r(err, buf, sizeof(buf));
    if (tmp == -1)
    {
        if (pfx && strcmp(pfx, "strerror_r (+ secondary error lost!)") == 0)
            strcpy(buf, "Error upon error upon error ...");
        else
            return strerror_with_prefix("strerror_r (+ secondary error lost!)", errno);
    }
    buf_len = strlen(buf);

    out_len = buf_len;
    if (pfx && *pfx)
    {
        pfx_len = strlen(pfx);
        out_len += 2 + pfx_len;
    }
    out = malloc(out_len + 1);
    p = out;
    if (pfx && *pfx)
    {
        memcpy(p, pfx, pfx_len);
        p += pfx_len;
        memcpy(p, ": ", 2);
        p += 2;
    }
    memcpy(p, buf, buf_len);
    p += buf_len;
    *p = '\0';
    return out;
}
static void strerror_with_prefix_fd(int fd, const char *pfx, int err)
{
    char buf[1024];
    int tmp;
#define OUT_VLEN 3
    struct iovec out[OUT_VLEN];
    int out_voff;

    tmp = correct_strerror_r(err, buf, sizeof(buf));
    if (tmp == -1)
    {
        if (pfx && strcmp(pfx, "strerror_r") == 0)
            strcpy(buf, "Error upon error upon error ...");
        else
        {
            strerror_with_prefix_fd(fd, "strerror_r", errno);
            return;
        }
    }

    if (pfx && *pfx)
    {
        out_voff = 0;
        out[0].iov_base = (char *)pfx;
        out[0].iov_len = strlen(pfx);
        out[1].iov_base = ": ";
        out[1].iov_len = 2;
    }
    else
    {
        out_voff = 2;
    }
    out[2].iov_base = buf;
    out[2].iov_len = strlen(buf);
    writev_fully(fd, out + out_voff, OUT_VLEN - out_voff);
}

/*
 * The common cachable case is a single file descriptor being assigned
 * to several adjacent file descriptor numbers, for example a TTY being
 * assigned to stdin, stdout, and stderr.
 *
 * Global variables are safe because this is only used in the grandchild.
 */
static int fcntl_cached_fd = -1;
static int fcntl_cached_flags;
static int fcntl_flags_cached(int fd)
{
    if (fd == fcntl_cached_fd)
        return fcntl_cached_flags;
    fcntl_cached_fd = fd;
    return fcntl_cached_flags = fcntl(fd, F_GETFD);
}

static int fcntl_set_cloexec(int fd)
{
    int old_flags = fcntl_flags_cached(fd);
    if (old_flags == -1)
        return -1;
    if (old_flags & FD_CLOEXEC)
        return 0;
    fcntl_cached_flags |= FD_CLOEXEC;
    return fcntl(fd, F_SETFD, old_flags | FD_CLOEXEC);
}
static int fcntl_unset_cloexec(int fd)
{
    int old_flags = fcntl_flags_cached(fd);
    if (old_flags == -1)
        return -1;
    if (!(old_flags & FD_CLOEXEC))
        return 0;
    fcntl_cached_flags &=~ FD_CLOEXEC;
    return fcntl(fd, F_SETFD, old_flags &~ FD_CLOEXEC);
}
static int fcntl_dupfd_cloexec(int fd, int nfds)
{
    return fcntl(fd, F_DUPFD_CLOEXEC, nfds);
}

static int sigchld_pipe[2] = {-1, -1};
#define sigchld_pipe_read sigchld_pipe[0]
#define sigchld_pipe_write sigchld_pipe[1]
static void sigchld_handler(int sig)
{
    char buf = sig;
    int status = write(sigchld_pipe_write, &buf, 1);
    if (status != 1)
    {
        /*
         * In the child handler, we don't have access to error_pipe_write.
         * Of course, if writing to *this* pipe failed ... wouldn't that?
         * (Not necessarily).
         */
        abort();
    }
}

/*
 * There are 3 processes involved:
 *  * "parent", the original process that calls this. It may have threads.
 *  * "child", the temporary process used for reparenting.
 *  * "grandchild", the final process that actually executes that target.
 *
 * Each process may leave in one of 3 ways:
 *  * "signal", by receiving an involuntary signal (most are blocked
 *    for better determinism, but not "true" SIGSEGVs and not abort()).
 *  * "error", if some syscall indicates failure. Note that some of these
 *    are necessarily transformed into signals.
 *  * "success", if everything works wonderfully (in that process).
 *
 * That makes 9 cases to handle:
 *  * "parent + signal": officially Somebody Else's Problem™.
 *  * "parent + error": return a malloc()'ed string containing the error.
 *  * "parent + success":
 *      * read error_pipe_read. If non-empty, return that as an error.
 *      * waitpid() for the (immediate) child. If it exits abnormally,
 *        return a generic error.
 *  * "child + signal": handled by the parent's unconditional waitpid().
 *  * "child + error": write the error to error_pipe_write, or signal.
 *  * "child + success":
 *      * normally, just _exit(0) after the fork. But ...
 *      * if the child dies *before* execve(), write that to
 *        error_pipe_write. This reqires poll() or similar.
 *  * "grandchild + signal": handled by the child's SIGCHLD handler.
 *  * "grandchild + error": write to error_pipe_write, then call _exit(0).
 *  * "grandchild + success": execve never returns.
 */
char *vterm_py_spawn_and_forget(char *cmd, char **argv, char **envp, int nfds, int *fds, int tty_fd)
{
    __attribute__((unused))
    int ignored;
    char *error_string = NULL;
    const char *what = NULL;
#define __ /* nothing, for C89 compatibility. */
#define C(ret, fn, args)                    \
    do {                                    \
        ssize_t _check_tmp = ret fn args;   \
        if (_check_tmp == -1)               \
        {                                   \
            what = #fn;                     \
            goto CURRENT_ERROR;             \
        }                                   \
    } while (0)
    sigset_t new_sigset, old_sigset;
    bool have_sigset = false;
    int error_pipe[2] = {-1, -1};
#define error_pipe_read error_pipe[0]
#define error_pipe_write error_pipe[1]
    pid_t parent_pid = -1, child_pid = -1, grandchild_pid = -1;
    void (*old_handler)(int);
    struct pollfd pfds[2];
    int empty_pipe[2] = {-1, -1};
#define empty_pipe_read empty_pipe[0]
#define empty_pipe_write empty_pipe[1]
    int i;

#define CURRENT_ERROR parent_error
    C(__, sigfillset, (&new_sigset));
    C(__, pthread_sigmask, (SIG_BLOCK, &new_sigset, &old_sigset));
    have_sigset = true;
    C(__, pipe2, (error_pipe, O_CLOEXEC));
    C(parent_pid =, getpid, ());
    C(child_pid =, fork, ());
    if (child_pid != 0)
    {
        /* We are still the parent. */
        char buf[32 + 2 + 1024 + 1];
        size_t off = 0;
        ignored = close(error_pipe_write); error_pipe_write = -1;
        while (off != sizeof(buf))
        {
            ssize_t rv;
            C(rv =, read, (error_pipe_read, buf + off, sizeof(buf) - off));
            if (rv == 0)
                break;
            off += rv;
        }
        ignored = close(error_pipe_read); error_pipe_read = -1;
        if (off)
        {
            error_string = malloc(off + 1);
            memcpy(error_string, buf, off);
            error_string[off] = '\0';
        }
        /* Parent's job is done, with no errors (probably)! Woo! */
        goto parent_out;
    }
#undef CURRENT_ERROR

#define CURRENT_ERROR child_error
    /* We are the child now. */
    old_handler = signal(SIGABRT, SIG_DFL);
    if (old_handler == SIG_ERR)
    {
        what = "signal SIGABRT";
        goto CURRENT_ERROR;
    }
    C(__, pipe2, (empty_pipe, O_CLOEXEC));
    C(grandchild_pid =, fork, ());
    if (grandchild_pid != 0)
    {
        ignored = close(empty_pipe_write); empty_pipe_write = -1;
        C(__, pipe, (sigchld_pipe));
        C(__, sigemptyset, (&new_sigset));
        C(__, sigaddset, (&new_sigset, SIGCHLD));
        C(__, pthread_sigmask, (SIG_UNBLOCK, &new_sigset, NULL));
        old_handler = signal(SIGCHLD, sigchld_handler);
        if (old_handler == SIG_ERR)
        {
            what = "signal SIGABRT";
            goto CURRENT_ERROR;
        }

        pfds[0].fd = sigchld_pipe_read;
        pfds[0].events = POLLIN;
        pfds[1].fd = empty_pipe_read;
        pfds[1].events = 0;
        while (true)
        {
            int status;
            C(status =, poll, (pfds, 2, -1));
            if (pfds[0].revents & POLLIN)
            {
                /* Child exited. */
                struct iovec out[4];
                size_t out_len = 0;
                char msg_int_buf[INT_STR_BUF_SIZE];
                C(__, waitpid, (grandchild_pid, &status, 0));
                /* They sent an error down the pipe already. */
                if (status == 0)
                    break;
                iov_append_str(out, &out_len, "grandchild ");
                iov_append_signal(out, &out_len, status, msg_int_buf);
                writev_fully(error_pipe_write, out, out_len);
                break;
            }
            if (pfds[1].revents & POLLHUP)
            {
                /*
                 * Child successfully execve'd *or* exited, but we would've
                 * gotten the above first (or simultaneously) if it exited.
                 * Not our problem anymore.
                 */
                break;
            }
        }
        goto child_out;
    }
#undef CURRENT_ERROR

#define CURRENT_ERROR grandchild_error
    /* Finally in the grandchild, we can get to work! */
    ignored = close(empty_pipe_read); empty_pipe_read = -1;
    C(__, setsid, ());
    /*
     * Never close any FD directly. It might occur as a source for more
     * than one child FD.
     */
    while (nfds > 0 && fds[nfds - 1] == -1)
        nfds--;
    if (error_pipe_write < nfds && fds[error_pipe_write] != -1)
    {
        int error_pipe_tmp;
        C(error_pipe_tmp =, fcntl_dupfd_cloexec, (error_pipe_write, nfds));
        error_pipe_write = error_pipe_tmp;
    }
    if (tty_fd != -1)
    {
        C(__, ioctl, (tty_fd, TIOCSCTTY, 0));
        /*
         * Arrange to close the tty_fd if we need to.
         * If there is a mapping, we don't need to.
         */
        if (tty_fd >= nfds || fds[tty_fd] == -1)
        {
            C(__, fcntl_set_cloexec, (tty_fd));
        }
    }
    for (i = 0; i < nfds; ++i)
    {
        /*
         * A pre-loop is needed to handle cases like {0: 1, 1: 0}.
         *
         * Specifically, for each such fd, dup it to something
         * guaranteed not to collide, then mark them both CLOEXEC.
         *
         * But while we're here, mark everything else as CLOEXEC (or not).
         */
        int fd_i;
        fd_i = fds[i];
        if (fd_i == -1)
            continue;
        /* {0: 0} */
        if (fd_i == i)
        {
            C(__, fcntl_unset_cloexec, (fd_i));
            continue;
        }
        /* {0: 0, 1: 0} */
        if (fd_i < nfds && fds[fd_i] == fd_i)
            continue;
        /* {0: 1, 1: N} */
        if (i < fd_i)
            continue;
        /* both branches for {0: N, 1: 0} */
        if (fd_i < nfds)
        {
            C(fds[i] = fd_i =, fcntl_dupfd_cloexec, (fd_i, nfds));
        }
        else
        {
            C(__, fcntl_set_cloexec, (fd_i));
        }
    }
    for (i = 0; i < nfds; ++i)
    {
        int fd_i = fds[i];
        if (fd_i == -1 || fd_i == i)
            continue;
        C(__, dup2, (fd_i, i));
    }
    C(__, pthread_sigmask, (SIG_SETMASK, &old_sigset, NULL));
    C(__, execvpe, (cmd, argv, envp));
    /* unreachable */
#undef CURRENT_ERROR
#undef C
grandchild_error:
    strerror_with_prefix_fd(error_pipe_write, what, errno);
    _exit(0);

child_error:
    strerror_with_prefix_fd(error_pipe_write, what, errno);
child_out:
    _exit(0);

parent_error:
    error_string = strerror_with_prefix(what, errno);
parent_out:
    if (child_pid != -1)
    {
        int status;
        int tmp = waitpid(child_pid, &status, 0);
        if (tmp == -1)
        {
            if (error_string)
            {
                free(error_string);
                error_string = strerror_with_prefix("waitpid (+ secondary error lost!)", errno);
            }
            else
            {
                error_string = strerror_with_prefix("waitpid", errno);
            }
        }
        else if (status)
        {
            struct iovec out[5];
            size_t out_len = 0;
            char msg_int_buf[INT_STR_BUF_SIZE];
            iov_append_str(out, &out_len, "child ");
            iov_append_signal(out, &out_len, status, msg_int_buf);
            if (error_string)
            {
                iov_append_str(out, &out_len, " (+ secondary error lost!)");
                free(error_string);
            }
            error_string = iov_to_str(out, out_len);
        }
    }
    if (error_pipe_read != -1)
        ignored = close(error_pipe_read);
    if (error_pipe_write != -1)
        ignored = close(error_pipe_write);
    if (have_sigset)
        ignored = pthread_sigmask(SIG_SETMASK, &old_sigset, NULL);
    return error_string;
}
