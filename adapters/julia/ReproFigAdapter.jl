module ReproFigAdapter
export promote, savefig_verified

function promote(candidate, record, workspace, destination, policy;
                 semantic_bindings=nothing, name=nothing)
    args = ["broker", "promote", candidate, "--workspace", workspace,
            "--destination", destination, "--policy", policy, "--record", record]
    if semantic_bindings !== nothing
        append!(args, ["--semantic-bindings", semantic_bindings])
    end
    if name !== nothing
        append!(args, ["--name", name])
    end
    run(Cmd(["reprofig"; args]))
end

function savefig_verified(plot, candidate, record, workspace, destination, policy;
                          semantic_bindings=nothing)
    savefig(plot, candidate)
    promote(candidate, record, workspace, destination, policy;
            semantic_bindings=semantic_bindings)
end
end
