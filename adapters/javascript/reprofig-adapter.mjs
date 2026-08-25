import { spawnSync } from "node:child_process";

export function promote({candidate, record, semanticBindings, workspace, destination, policy, name}) {
  const args = ["broker", "promote", candidate, "--workspace", workspace,
                "--destination", destination, "--policy", policy,
                "--record", record];
  if (semanticBindings) args.push("--semantic-bindings", semanticBindings);
  if (name) args.push("--name", name);
  const result = spawnSync("reprofig", args, {stdio: "inherit"});
  if (result.status !== 0) throw new Error("ReproFig broker rejected the candidate");
}
