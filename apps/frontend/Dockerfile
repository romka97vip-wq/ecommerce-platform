# Этап 1: builder 
FROM node:20-alpine AS builder

WORKDIR /build

COPY index.html .

# Этап 2: финальный (nginx раздает)
FROM nginx:alpine

COPY --from=builder /build/index.html /usr/share/nginx/html/index.html

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
