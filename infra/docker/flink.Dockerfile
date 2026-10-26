FROM flink:1.20.2-scala_2.12-java17 AS flink-runtime

ARG KAFKA_CONNECTOR_VERSION=3.3.0-1.20
ARG KAFKA_CONNECTOR_SHA1=9e7e2bb762e6cb489bcc76f2637e824fbb6f08c3
ARG ZSTD_JNI_VERSION=1.5.6-3
ARG ZSTD_JNI_SHA1=823b794106e4bcb80110f49408d1641231f25927

USER root

RUN connector="flink-sql-connector-kafka-${KAFKA_CONNECTOR_VERSION}.jar" \
    && curl --fail --show-error --silent --location \
      "https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONNECTOR_VERSION}/${connector}" \
      --output "/opt/flink/lib/${connector}" \
    && echo "${KAFKA_CONNECTOR_SHA1}  /opt/flink/lib/${connector}" | sha1sum --check --status \
    && zstd="zstd-jni-${ZSTD_JNI_VERSION}.jar" \
    && curl --fail --show-error --silent --location \
      "https://repo1.maven.org/maven2/com/github/luben/zstd-jni/${ZSTD_JNI_VERSION}/${zstd}" \
      --output "/opt/flink/lib/${zstd}" \
    && echo "${ZSTD_JNI_SHA1}  /opt/flink/lib/${zstd}" | sha1sum --check --status \
    && mkdir -p /opt/flink/plugins/s3-fs-hadoop \
    && cp /opt/flink/opt/flink-s3-fs-hadoop-1.20.2.jar /opt/flink/plugins/s3-fs-hadoop/

USER flink

FROM eclipse-temurin:17-jdk-jammy AS udf-builder

COPY --from=flink-runtime /opt/flink/lib /flink-lib
COPY infra/flink/java /src

RUN mkdir -p /classes \
    && javac -cp '/flink-lib/*' -d /classes \
      /src/org/cognitivetraffic/flink/RollingEventTimeMeans.java \
    && jar --create --file /traffic-features-udf.jar -C /classes .

FROM flink-runtime

USER root

COPY --from=udf-builder /traffic-features-udf.jar /opt/flink/lib/traffic-features-udf.jar

RUN chown flink:flink /opt/flink/lib/traffic-features-udf.jar

USER flink
