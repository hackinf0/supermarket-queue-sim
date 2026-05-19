import logging
import random

from discrete_event_sim import Simulation , Event
from collections import deque

class CarWash(Simulation):
    def __init__(self,lambd,mu,max_cars,d,num_postes):
        super().__init__()
        self.car_washed_count=0
        self.car_next_id=0
        self.lambd=lambd
        self.mu=mu
        self.max_cars=max_cars
        self.total_wait = 0.
        self.num_postes=num_postes
        self.washing=[None]*num_postes
        self.car_queues= [deque() for _ in range(num_postes)]
        self.d=d
    def queue_len(self,i):
        return (self.washing[i] is not None) + len(self.car_queues[i])
    
class Arrival(Event):
    def __init__(self, id, arrival_time):
        self.id = id
        self.arrival_time = arrival_time

    def process(self, sim):
        sim.log_info("Car arrived")
        choix_postes= random.sample(range(sim.num_postes),sim.d)
        poste=min(choix_postes,key=sim.queue_len)
        if sim.washing[poste] is None:
            sim.washing[poste]=self.id
            sim.schedule(random.expovariate(sim.mu),Departure(self.id, self.arrival_time,poste))
        
        else:
            sim.log_info("Car in queue")
            self.poste_id = poste
            sim.car_queues[poste].append(self)
            
        if sim.car_next_id < sim.max_cars - 1:
            sim.car_next_id += 1
            delay = random.expovariate(sim.lambd)
            sim.schedule(delay, Arrival(sim.car_next_id, sim.t + delay))

class Departure(Event):
    def __init__(self, id, arrival_time,poste_id):
        self.id = id
        self.arrival_time = arrival_time
        self.poste_id=poste_id
        
    def process(self, sim):
        wait = sim.t - self.arrival_time
        sim.total_wait += wait
        sim.log_info("Car washed")
        sim.car_washed_count+=1
        poste = self.poste_id
        if sim.car_queues[poste]:
            car=sim.car_queues[poste].popleft()
            sim.washing[poste] = car.id
            sim.schedule(random.expovariate(sim.mu),Departure(car.id,car.arrival_time,car.poste_id))
            
        else:
                sim.washing[poste] = None
            
            
            
            
#logging.basicConfig(level=logging.INFO)

lambd, mu = 9, 1
sim = CarWash(lambd, mu, 5000, 2, 10)
sim.schedule(0, Arrival(0, 0))
sim.run()

avg_wait = sim.total_wait / sim.car_washed_count
theory = 1 / (mu - lambd)
print(f'Served {sim.car_washed_count} customers')
print(f'Average time in system: {avg_wait:.2f}  ( {sim.num_postes} postes ,d={sim.d})')
print(f'Cars still in queue: {sum(len(q) for q in sim.car_queues)}')