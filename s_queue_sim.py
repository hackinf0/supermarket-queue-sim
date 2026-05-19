#!/usr/bin/env python3
from matplotlib import pyplot as plt
import argparse
import csv
from collections import deque, Counter
import logging
from random import expovariate, sample, seed

from discrete_event_sim import Simulation, Event
from workloads import weibull_generator, parse_mustang, normalize_trace

CSV_COLUMNS = ['lambd', 'mu', 'max_t', 'n', 'd', 'w']


class Queues(Simulation):
    def __init__(self, lambd, mu, n, d, weibull_shape_arrival, weibull_shape_service, use_lwl=False, trace=None):
        super().__init__()
        self.running = [None] * n
        self.queues = [deque() for _ in range(n)]
        self.next_id = 0
        self.arrivals = {}
        self.completions = {}
        self.lambd = lambd
        self.n = n
        self.d = d
        self.mu = mu
        self.job_sizes = {}
        self.completion_times = {}
        self.wait_times = []
        self.use_lwl = use_lwl
        self.queue_lengths = Counter()
        self.weibull_shape_arrival = weibull_shape_arrival
        self.weibull_shape_service = weibull_shape_service
        self.trace = trace
        self._trace_exhausted = False

        if trace is not None:
            self._delays = iter(d for d, _ in trace)
            self._sizes  = iter(s for _, s in trace)
            first_delay  = next(self._delays)
            self.arrival_gen = None
            self.service_gen = None
        else:
            self._delays = None
            self._sizes  = None
            first_delay  = weibull_generator(weibull_shape_arrival, 1 / (lambd * n))()
            self.arrival_gen = weibull_generator(weibull_shape_arrival, 1 / (lambd * n))
            self.service_gen = weibull_generator(weibull_shape_service, 1 / mu)

        self.schedule(first_delay, Arrival(0))
        self.schedule(0, Monitor())

    def schedule_arrival(self, job_id):
        if self._delays is not None:
            try:
                delay = next(self._delays)
            except StopIteration:
                self._trace_exhausted = True
                return
            self.schedule(delay, Arrival(job_id))
        else:
            self.schedule(self.arrival_gen(), Arrival(job_id))

    def schedule_completion(self, job_id, queue_index):
        if self._sizes is not None:
            try:
                size = next(self._sizes)
            except StopIteration:
                self._trace_exhausted = True
                return
            service_time = size
        else:
            service_time = self.service_gen()

        self.job_sizes[job_id] = service_time
        self.completion_times[job_id] = self.t + service_time
        self.schedule(service_time, Completion(job_id, queue_index))

    def queue_len(self, i):
        return (self.running[i] is not None) + len(self.queues[i])

    def queue_work(self, i):
        total = 0.0
        if self.running[i] is not None:
            job_id = self.running[i]
            total += self.completion_times[job_id] - self.t
        for job_id in self.queues[i]:
            total += self.job_sizes[job_id]
        return total


class Arrival(Event):
    def __init__(self, job_id):
        self.id = job_id

    def process(self, sim: Queues):
        if sim._trace_exhausted:
            return
        sim.arrivals[self.id] = sim.t
        sample_queues = sample(range(sim.n), sim.d)

        if sim.use_lwl:
            queue_index = min(sample_queues, key=sim.queue_work)
        else:
            queue_index = min(sample_queues, key=sim.queue_len)

        if sim.running[queue_index] is None:
            sim.running[queue_index] = self.id
            sim.schedule_completion(self.id, queue_index)
        else:
            sim.queues[queue_index].append(self.id)

        sim.next_id += 1
        sim.schedule_arrival(sim.next_id)


class Completion(Event):
    def __init__(self, job_id, queue_index):
        self.job_id = job_id
        self.queue_index = queue_index

    def process(self, sim: Queues):
        queue_index = self.queue_index
        assert sim.running[queue_index] == self.job_id
        sim.completions[self.job_id] = sim.t
        wait = (sim.t - sim.arrivals[self.job_id]) - sim.job_sizes[self.job_id]
        sim.wait_times.append(wait)
        queue = sim.queues[queue_index]
        if queue:
            sim.running[queue_index] = new_job_id = queue.popleft()
            sim.schedule_completion(new_job_id, queue_index)
        else:
            sim.running[queue_index] = None


class Monitor(Event):
    def __init__(self, interval=1):
        self.interval = interval

    def process(self, sim):
        for i in range(sim.n):
            sim.queue_lengths[sim.queue_len(i)] += 1
        sim.schedule(self.interval, self)


def theoretical(i, lambd, d):
    if d == 1:
        return lambd ** i
    exponent = (d**i - 1) / (d - 1)
    return lambd ** exponent


def run_simulation(lambd, d, n, max_t, weibull_shape_arrival=1, weibull_shape_service=1, use_lwl=False):
    sim = Queues(lambd, 1, n, d, weibull_shape_arrival, weibull_shape_service, use_lwl=use_lwl)
    sim.run(max_t)
    counter = sim.queue_lengths
    total = sum(counter.values())
    fractions = []
    for x in range(1, 15):
        at_least_x = sum(count for length, count in counter.items() if length >= x)
        fractions.append(at_least_x / total)
    return sum(sim.wait_times) / len(sim.wait_times), fractions


def run_simulation_trace(trace, d, n, use_lwl=False):
    sim = Queues(None, None, n, d, None, None, use_lwl=use_lwl, trace=trace)
    sim.run(float('inf'))
    if not sim.wait_times:
        return 0.0
    return sum(sim.wait_times) / len(sim.wait_times)


def print_table(fractions, theo, lambd, d):
    print(f"Queue Size Distribution (Experimental vs. Theoretical) -- d = {d}, lambd = {lambd}:")
    print(f"{'Queue Size':<12}{'Experimental':<20}{'Theoretical':<20}")
    print("-" * 50)
    print(f"{0:<12}{1.0:<20.5f}{1.0:<20.5f}")
    for x in range(1, 15):
        print(f"{x:<12}{fractions[x-1]:<20.5f}{theo[x-1]:<20.5f}")
    print()


def plot_curve(ax, fractions, theo, lambd):
    xs = range(1, 15)
    line, = ax.plot(xs, fractions, label=f'λ = {lambd}')
    ax.plot(xs, theo, linestyle='--', color=line.get_color())


def plot_comparison(n, max_t, d):
    lambdas = [0.5, 0.7, 0.9, 0.95, 0.99]
    ks = [2.0, 1.0, 0.5]

    fig, ax = plt.subplots(figsize=(10, 6))

    for k in ks:
        results_sq  = []
        results_lwl = []
        for lambd in lambdas:
            wait_sq,  _ = run_simulation(lambd, d, n, max_t, weibull_shape_service=k, use_lwl=False)
            wait_lwl, _ = run_simulation(lambd, d, n, max_t, weibull_shape_service=k, use_lwl=True)
            results_sq.append(wait_sq)
            results_lwl.append(wait_lwl)
            print(f"λ={lambd:.2f} | k={k} | SQ={wait_sq:.4f} | LWL={wait_lwl:.4f}")
        line, = ax.plot(lambdas, results_sq,  marker='o', label=f'SQ (k={k})')
        ax.plot(lambdas, results_lwl, marker='s', linestyle='--', color=line.get_color(), label=f'LWL (k={k})')

    ax.set_title(f'SQ vs LWL — Average Waiting Time (d={d})')
    ax.set_xlabel('λ (load)')
    ax.set_ylabel('Average waiting time')
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.show()


def plot_comparison_mustang(n, d):
    lambdas = [0.5, 0.7, 0.9, 0.95, 0.99]
    results_sq  = []
    results_lwl = []

    raw_trace = parse_mustang()

    for lambd in lambdas:
        trace = normalize_trace(raw_trace, lambd)
        wait_sq  = run_simulation_trace(trace, d, n, use_lwl=False)
        wait_lwl = run_simulation_trace(trace, d, n, use_lwl=True)
        results_sq.append(wait_sq)
        results_lwl.append(wait_lwl)
        print(f"λ={lambd:.2f} | SQ={wait_sq:.4f} | LWL={wait_lwl:.4f}")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(lambdas, results_sq,  marker='o', label='SQ (Mustang)')
    ax.plot(lambdas, results_lwl, marker='s', linestyle='--', label='LWL (Mustang)')
    ax.set_title(f'SQ vs LWL — Mustang Trace (d={d})')
    ax.set_xlabel('λ (load)')
    ax.set_ylabel('Average waiting time')
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--lambd', type=float, default=0.7)
    parser.add_argument('--mu', type=float, default=1)
    parser.add_argument('--max-t', type=float, default=1_000_000)
    parser.add_argument('--n', type=int, default=1)
    parser.add_argument('--d', type=int, default=1)
    parser.add_argument('--csv', help="CSV file in which to store results")
    parser.add_argument("--seed", help="random seed")
    parser.add_argument("--verbose", action='store_true')
    parser.add_argument('--weibull-shape-arrival', type=float, default=1.0)
    parser.add_argument('--weibull-shape-service', type=float, default=1.0)
    parser.add_argument('--mustang', action='store_true', help="Use Mustang trace instead of Weibull")
    args = parser.parse_args()

    if args.seed:
        seed(args.seed)

    if args.mustang:
        plot_comparison_mustang(100, args.d)
    else:
        plot_comparison(100, 100000, args.d)

    plt.show()


if __name__ == '__main__':
    main()