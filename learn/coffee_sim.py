from collections import deque
import random
from discrete_event_sim import Simulation, Event
import logging


class CoffeeShop(Simulation):
    def __init__(self, lambd, mu, max_customers):
        super().__init__()
        self.customers_served = 0
        self.busy = False
        self.my_queue = deque()
        self.next_id = 0
        self.lambd = lambd
        self.mu = mu
        self.max_customers = max_customers
        self.total_wait = 0.0


class Arrival(Event):
    def __init__(self, id, arrival_time):
        self.id = id
        self.arrival_time = arrival_time

    def process(self, sim):
        sim.log_info(f"customer {self.id} arrived")
        if not sim.busy:
            sim.busy = True
            sim.schedule(random.expovariate(sim.mu), Departure(self.id, self.arrival_time))
        else:
            sim.log_info(f"customer {self.id} queued")
            sim.my_queue.append(self)
        if sim.next_id < sim.max_customers - 1:
            sim.next_id += 1
            delay = random.expovariate(sim.lambd)
            sim.schedule(delay, Arrival(sim.next_id, sim.t + delay))


class Departure(Event):
    def __init__(self, id, arrival_time):
        self.id = id
        self.arrival_time = arrival_time

    def process(self, sim):
        wait = sim.t - self.arrival_time
        sim.total_wait += wait
        sim.customers_served += 1
        sim.log_info(f"customer {self.id} left after {wait:.2f}")
        if sim.my_queue:
            customer = sim.my_queue.popleft()
            sim.schedule(random.expovariate(sim.mu), Departure(customer.id, customer.arrival_time))
        else:
            sim.busy = False



logging.basicConfig(level=logging.INFO, filename='coffee_log.txt', filemode='w')
lambd, mu = 0.2, 0.3
sim = CoffeeShop(lambd, mu, 1000)
sim.schedule(0, Arrival(0, 0))
sim.run()

avg_wait = sim.total_wait / sim.customers_served
theory = 1 / (mu - lambd)
print(f'Served {sim.customers_served} customers')
print(f'Average time in system: {avg_wait:.2f}  (theory M/M/1: {theory:.2f})')