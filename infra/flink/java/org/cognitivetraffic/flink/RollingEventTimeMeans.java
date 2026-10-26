package org.cognitivetraffic.flink;

import java.io.Serializable;
import java.time.Instant;
import java.util.Arrays;

import org.apache.flink.table.functions.AggregateFunction;

/** Event-time means evaluated inside the common 60-minute SQL OVER frame. */
public final class RollingEventTimeMeans {
    private RollingEventTimeMeans() {}

    public static final class Accumulator implements Serializable {
        public long[] timestamps = new long[16];
        public double[] speeds = new double[16];
        public int size;
    }

    private abstract static class MeanWithin extends AggregateFunction<Double, Accumulator> {
        private final long lookbackMillis;

        MeanWithin(long lookbackMillis) {
            this.lookbackMillis = lookbackMillis;
        }

        @Override
        public Accumulator createAccumulator() {
            return new Accumulator();
        }

        public void accumulate(Accumulator accumulator, Instant eventTime, Double speedKmh) {
            if (eventTime == null || speedKmh == null) {
                return;
            }
            ensureCapacity(accumulator, accumulator.size + 1);
            accumulator.timestamps[accumulator.size] = eventTime.toEpochMilli();
            accumulator.speeds[accumulator.size] = speedKmh;
            accumulator.size++;
        }

        public void retract(Accumulator accumulator, Instant eventTime, Double speedKmh) {
            if (eventTime == null || speedKmh == null) {
                return;
            }
            long timestamp = eventTime.toEpochMilli();
            for (int index = 0; index < accumulator.size; index++) {
                if (accumulator.timestamps[index] == timestamp
                        && Double.compare(accumulator.speeds[index], speedKmh) == 0) {
                    int last = accumulator.size - 1;
                    accumulator.timestamps[index] = accumulator.timestamps[last];
                    accumulator.speeds[index] = accumulator.speeds[last];
                    accumulator.size = last;
                    return;
                }
            }
        }

        @Override
        public Double getValue(Accumulator accumulator) {
            if (accumulator.size == 0) {
                return null;
            }
            long currentEventTime = Long.MIN_VALUE;
            for (int index = 0; index < accumulator.size; index++) {
                currentEventTime = Math.max(currentEventTime, accumulator.timestamps[index]);
            }
            long cutoff = currentEventTime - lookbackMillis;
            double sum = 0.0;
            int count = 0;
            for (int index = 0; index < accumulator.size; index++) {
                if (accumulator.timestamps[index] >= cutoff) {
                    sum += accumulator.speeds[index];
                    count++;
                }
            }
            return count == 0 ? null : sum / count;
        }

        private static void ensureCapacity(Accumulator accumulator, int requiredCapacity) {
            if (requiredCapacity <= accumulator.timestamps.length) {
                return;
            }
            int capacity = Math.max(requiredCapacity, accumulator.timestamps.length * 2);
            accumulator.timestamps = Arrays.copyOf(accumulator.timestamps, capacity);
            accumulator.speeds = Arrays.copyOf(accumulator.speeds, capacity);
        }
    }

    public static final class Mean15m extends MeanWithin {
        public Mean15m() {
            super(15 * 60 * 1000L);
        }
    }

    public static final class Mean30m extends MeanWithin {
        public Mean30m() {
            super(30 * 60 * 1000L);
        }
    }
}
