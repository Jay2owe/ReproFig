# Thin, opt-in R adapter: the Python broker remains the verification authority.
reprofig_promote <- function(candidate, record, workspace, destination, policy,
                             semantic_bindings=NULL, output_name=NULL) {
  args <- c("broker", "promote", candidate, "--workspace", workspace,
            "--destination", destination, "--policy", policy,
            "--record", record)
  if (!is.null(semantic_bindings)) args <- c(args, "--semantic-bindings", semantic_bindings)
  if (!is.null(output_name)) args <- c(args, "--name", output_name)
  status <- system2("reprofig", args)
  if (status != 0) stop("ReproFig broker rejected the candidate")
  invisible(status)
}

reprofig_ggsave <- function(filename, plot, ..., record, workspace, destination,
                            policy, semantic_bindings=NULL) {
  ggplot2::ggsave(filename=filename, plot=plot, ...)
  reprofig_promote(filename, record, workspace, destination, policy,
                   semantic_bindings=semantic_bindings)
}
