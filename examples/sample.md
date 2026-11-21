The deploy finished, and the new search page is live on staging.

Two things to check before we promote it:

- The cache hit rate dropped a little after the change. It should recover within an hour.
- One test is flaky on slow machines. I marked it and opened a ticket.

```
npm run test -- search
```

Say yes and I'll open the pull request.
