#!/bin/bash

for shape_service in 1.0 0.5 2.0; do
    python w_queue_sim.py --d 2 --n 100 --max-t 100000 \
        --weibull-shape-arrival 1.0 \
        --weibull-shape-service $shape_service
done