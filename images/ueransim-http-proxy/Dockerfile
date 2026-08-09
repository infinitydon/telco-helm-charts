FROM golang:1.24.6-alpine3.22 AS build

WORKDIR /src
COPY go.mod main.go main_test.go ./
RUN go test ./... && CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -trimpath -ldflags="-s -w" -o /out/ueransim-http-proxy .

FROM alpine:3.21
RUN apk add --no-cache ca-certificates \
    && addgroup -g 10001 proxy \
    && adduser -D -H -u 10001 -G proxy proxy
COPY --from=build /out/ueransim-http-proxy /usr/local/bin/ueransim-http-proxy
USER 10001:10001
EXPOSE 8118
ENTRYPOINT ["/usr/local/bin/ueransim-http-proxy"]
