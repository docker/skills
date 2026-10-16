## Destructive Docker commands

Before running any Docker command that deletes or irreversibly changes state —
`docker rm`/`rm -f`, `docker kill`, any `prune`, `docker rmi`, `docker volume rm`,
`docker network rm`, `docker compose down -v`, `sbx rm`, `sbx prune` — state
exactly what will be lost and get explicit confirmation from the user first.
Prefer the narrowest command that solves the problem. Do not treat a request to
"clean up" or "start fresh" as consent to delete volumes or other data.
When the user names a specific resource and explicitly asks for that action on
it, you may carry it out without asking again; touch nothing else. You may also
remove a container you created yourself in this session, with no unsaved state,
without asking.
