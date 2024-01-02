BASE_URL=http://localhost:8000

P_AUTHOR="ckjackslack"
P_SINCE="2023-12-05"
P_UNTIL="2023-12-08"

A_PARAMS=(author since until)

PARAMS=""
for param in "${A_PARAMS[@]}"  # iterate over values
do
    var="P_"${param^^}  # uppercase
    PARAMS+="&${param}="${!var}  # concatenate; lookup variable from string contents
done
PARAMS=${PARAMS#?}  # skip first char

doreq() {
    full_url=${BASE_URL}/$1
    if [ $# -eq 2 ]  # check if number of parameters is equal to two
    then
        full_url+=?$2
    fi
    echo "Requesting: ${full_url}"
    curl -s -X GET $full_url | python -m json.tool
}

doreq
echo
doreq "commits" $PARAMS
