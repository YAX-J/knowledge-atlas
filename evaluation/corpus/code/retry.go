package eval

const maxRetries = 4

func retryDelay(attempt int) int {
    return 1 << attempt
}
