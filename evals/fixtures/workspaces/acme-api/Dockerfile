FROM node:22.20.0-alpine3.22@sha256:dbcedd8aeab47fbc0f4dd4bffa55b7c3c729a707875968d467aaaea42d6225af
ARG BUILD_REV=0
WORKDIR /app
COPY package.json server.js ./
RUN echo "$BUILD_REV" > /app/.build-rev
USER node
EXPOSE 3000
CMD ["node", "server.js"]
