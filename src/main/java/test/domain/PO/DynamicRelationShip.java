package test.domain.PO;

import lombok.Data;
import org.neo4j.ogm.annotation.*;

import java.util.List;

@Data
@RelationshipEntity(type = "ACTED_IN")
public class DynamicRelationShip<S extends BaseNode, E extends BaseNode> extends BaseRelationShip {
    @Property
    private List<String> roles;

    @StartNode
    private S startNode;

    @EndNode
    private E endNode;
}
