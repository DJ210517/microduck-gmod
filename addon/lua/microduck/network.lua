-- Exact feed-forward evaluation of the upstream ONNX graph, including normalization.
local N = {}
local exp = math.exp
function N.new(weights)
    assert(#weights.mean == 61 and #weights.layers == 4, "Invalid MicroDuck policy")
    return setmetatable({weights = weights, buffers = {{},{},{},{},{}}}, {__index=N})
end
function N:forward(obs)
    assert(#obs == 61, "MicroDuck needs 61 observations")
    local w = self.weights
    local x = self.buffers[1]
    for i=1,61 do x[i]=(obs[i]-w.mean[i])/w.divisor[i] end
    for k=1,4 do
        local l=w.layers[k]
        local y=self.buffers[k+1]
        local width=l.inputs
        local matrix,bias=l.w,l.b
        for i=1,l.outputs do
            local v=bias[i]
            local offset=(i-1)*width
            for j=1,width do v=v+matrix[offset+j]*x[j] end
            if k<4 and v<0 then v=exp(v)-1 end
            y[i]=v
        end
        x=y
    end
    return x
end
return N
