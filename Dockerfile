FROM maven:3.9.12-eclipse-temurin-21

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip ffmpeg nodejs npm \
    && python3 -m pip install --break-system-packages --no-cache-dir "yt-dlp[default]" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pom.xml .
RUN mvn -q -DskipTests dependency:go-offline
COPY src ./src
RUN mvn -q -DskipTests package

EXPOSE 8080
CMD ["sh", "-c", "java -Dserver.port=${PORT:-8080} -jar target/video-downloader-1.0.0.jar"]
