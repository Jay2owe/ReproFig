function reprofig_adapter(candidate, record, workspace, destination, policy, semantic_bindings, output_name)
% Thin, opt-in MATLAB adapter; exportgraphics/saveas remains caller-controlled.
args = sprintf('reprofig broker promote "%s" --workspace "%s" --destination "%s" --policy "%s" --record "%s"', ...
    candidate, workspace, destination, policy, record);
if nargin >= 6 && ~isempty(semantic_bindings)
    args = sprintf('%s --semantic-bindings "%s"', args, semantic_bindings);
end
if nargin >= 7 && ~isempty(output_name)
    args = sprintf('%s --name "%s"', args, output_name);
end
status = system(args);
if status ~= 0
    error('ReproFig broker rejected the candidate');
end
end
