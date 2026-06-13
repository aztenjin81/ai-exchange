FROM node:22-alpine AS base
WORKDIR /app
COPY package.json .

FROM base AS deps
RUN npm ci

FROM deps AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

FROM deps AS build
COPY . .
RUN npm run build

FROM node:22-alpine AS production
WORKDIR /app
COPY --from=build /app/build build/
COPY --from=build /app/package.json .
EXPOSE 3000
CMD ["node", "build/index.js"]
