package test.domain.PO;

import lombok.Data;
import org.neo4j.ogm.annotation.*;
import java.util.List;

@Data
@RelationshipEntity("ACTED_IN")
public class ACTED_IN extends BaseRelationShip {
    @Property(name = "roles")
    private List<String> roles;

    @StartNode
    private Person person;

    @EndNode
    private Movie movie;
}
