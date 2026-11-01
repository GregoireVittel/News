# Working on this repo

## Shipping changes
When the owner asks for an improvement or change, ship it all the way to `main`
without asking for confirmation:

1. Make the change on the working branch, with tests, and run the fast checks:
   `python -m unittest discover -s tests -p 'test_build*.py'` and
   `node --test tests/*.test.cjs`.
2. Push the branch, open a pull request, wait for the **Tests** check to pass,
   then squash-merge it into `main`.
3. Run the **Daily static edition** workflow (`daily-edition.yml`) on `main` so
   the live site (https://gregoirevittel.github.io/News/) is rebuilt and deployed,
   and confirm the run succeeds (check its log for unavailable feeds).

The live site only changes after that workflow runs; merging alone does not
republish it.
