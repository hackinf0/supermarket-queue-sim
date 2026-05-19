#!/bin/bash
for d in 1 2 5 10; do
    python m_queue_sim.py --d $d --n 100 --max-t 100000
done